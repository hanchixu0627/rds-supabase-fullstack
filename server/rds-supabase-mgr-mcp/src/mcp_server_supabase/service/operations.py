"""Implemented operations only; unsupported actions stay explicit."""
import os
import asyncio
import time
from mcp_server_supabase.service.jobs import job_result
from mcp_server_supabase.failures import RecoveryError
from mcp_server_supabase.service.plans import PlanStore, fingerprint
from mcp_server_supabase.service.network_contracts import ssl_followup
from huaweicloud_mcp_core.errors import McpToolError
from mcp_server_supabase.client.rest import segment
from mcp_server_supabase.client.sdk_core import configured_client
from mcp_server_supabase.service.contracts import api_key_query, key_metadata, ssl_body, accepted_job

ROOT = "/v3/{project}/ai-application"


def safe(value, depth=0):
    if depth > 8:
        return "[truncated]"
    if isinstance(value, dict):
        return {k: safe(v, depth+1) for k,v in value.items() if not any(s in k.lower() for s in ("password", "pwd", "secret", "token", "api_key")) and k.lower() not in ("ak", "sk")}
    if isinstance(value, list):
        return [safe(v, depth+1) for v in value[:100]]
    if isinstance(value, str):
        return value[:2000]
    return value


class Operations:
    def __init__(self, client=None, plans=None):
        self.client = client or configured_client()
        self.plans = plans or PlanStore()

    def app(self, application_id):
        return ROOT + "/" + segment(application_id) + "/supabase"

    def intent_digest(self, method, path, body):
        return fingerprint({"endpoint":self.client.endpoint,"project":self.client.project,
                            "credential":fingerprint(self.client.token if self.client.token is not None else os.getenv("HUAWEICLOUD_AUTH_TOKEN", "")),
                            "method":method,"path":path,"body":body})

    async def reconcile_auth(self, plan_id, application_id, expected):
        # Local ledger write + cloud reads only. No replay, cloud write, or arbitrary job ID.
        if os.getenv("HUAWEICLOUD_MCP_READ_ONLY", "false").lower() == "true":
            raise McpToolError("MCP_READ_ONLY", "Local ledger updates are disabled")
        if not expected or any(k not in ('enable_account_sign_up','enable_anonymous_users') or type(v) is not bool for k,v in expected.items()):
            raise McpToolError("MCP_INVALID_ARGS", "Supply exactly the original registration boolean changes")
        path=self.app(application_id)
        digest=self.intent_digest('PUT',path+'/auth-config',expected)
        record=self.plans.record(plan_id)
        if record['state']!='accepted' or record['digest']!=digest or not record['job_id']:
            raise McpToolError('MCP_GUARDRAIL_BLOCKED','Only an accepted matching Auth plan with its recorded job can be reconciled')
        task=await self.job(record['job_id'])
        if task['task_status']!='completed':
            raise McpToolError('MCP_GUARDRAIL_BLOCKED','Recorded task is not demonstrably completed')
        _, target=await self.client.request('GET',path)
        if not isinstance(target,dict) or target.get('id')!=application_id or target.get('status')!='normal' or target.get('current_actions'):
            raise McpToolError('MCP_GUARDRAIL_BLOCKED','Application identity or readiness is not verified')
        _, actual=await self.client.request('GET',path+'/auth-config')
        if not isinstance(actual,dict) or any(type(actual.get(k)) is not bool or actual[k] != value for k,value in expected.items()):
            raise McpToolError('MCP_GUARDRAIL_BLOCKED','Auth resource state does not match the recorded intent')
        result=self.plans.verify_auth(plan_id,digest,record['job_id'])
        return {**result,'cloud_writes_performed':False,
                'note':'Resource values were observed at resource_checked_at; business behavior is unverified. A later change still needs a new preview and confirmation.'}

    async def read(self, kind, application_id=None, limit=10, offset=0, **key_filters):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise McpToolError("MCP_INVALID_ARGS", "Invalid pagination")
        query = None
        if kind == "applications":
            path, query = ROOT + "/applications", {"limit":limit, "offset":offset, "type":"supabase"}
        else:
            path = self.app(application_id)
            if kind == "keys":
                path += "/api-keys"
                try:
                    query = api_key_query(limit, offset, **key_filters)
                except (ValueError, TypeError):
                    raise McpToolError("MCP_INVALID_ARGS", "Invalid key filters",
                                       hint="Use the supported metadata filter values.") from None
            elif kind == "auth":
                path += "/auth-config"
            elif kind != "application":
                raise McpToolError("MCP_INVALID_ARGS", "Unsupported query")
        _, data = await self.client.request("GET", path, query=query)
        if kind == "keys":
            try:
                data = key_metadata(data)
            except ValueError:
                raise McpToolError("MCP_SDK_ERROR", "Unrecognized key metadata response",
                                   hint="Verify the endpoint response contract before continuing.") from None
        return {"data":safe(data), "limit":limit, "note":"Output capped at 100 entries per array; use pagination. Secret fields excluded."}

    async def job(self, job_id):
        job_id = segment(job_id)
        _, data = await self.client.request("GET", "/v3/{project}/jobs", query={"id":job_id})
        return job_result(data, job_id)

    async def wait_job(self, job_id, max_attempts=3, interval_seconds=2, sleep=asyncio.sleep):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10 or type(interval_seconds) is not int or not 1 <= interval_seconds <= 5:
            raise McpToolError("MCP_INVALID_ARGS", "Use 1-10 observations and a 1-5 second interval")
        job_id = segment(job_id)
        deadline = time.monotonic() + 50
        result = job_result({}, job_id)
        attempts = 0
        exhausted = False
        for index in range(max_attempts):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                exhausted = True
                break
            attempts += 1
            try:
                result = await asyncio.wait_for(self.job(job_id), timeout=remaining)
            except asyncio.TimeoutError:
                exhausted = True
                break
            if result['task_status'] != 'running':
                break
            if index == max_attempts - 1:
                exhausted = True
                break
            await sleep(min(interval_seconds, max(0, deadline - time.monotonic())))
        return {**result, 'attempts':attempts, 'observation_exhausted':exhausted,
                'cloud_writes_performed':False}

    async def mutate(self, application_id, action, body, confirm=False, plan_id=None):
        path = self.app(application_id)
        reset_key_id = None
        if action == "ssl":
            try:
                body = ssl_body(**body)
            except (ValueError, TypeError):
                raise McpToolError("MCP_INVALID_ARGS", "Invalid SSL arguments") from None
            method, suffix = "POST", "/switch-ssl"
        elif action == "eip":
            if type(body.get("is_bind")) is not bool:
                raise McpToolError("MCP_INVALID_ARGS", "is_bind must be boolean")
            if body["is_bind"]:
                import ipaddress
                segment(body.get("public_ip_id"))
                try:
                    ipaddress.IPv4Address(body.get("public_ip_address"))
                except Exception:
                    raise McpToolError("MCP_INVALID_ARGS", "A valid public IPv4 address is required") from None
            else:
                if body.get("public_ip_id") is not None or body.get("public_ip_address") is not None:
                    raise McpToolError("MCP_INVALID_ARGS", "Unbinding must not include binding parameters",
                                       hint="Use is_bind=false with null or omitted EIP ID and address.")
                body = {"is_bind":False}
            method, suffix = "PUT", "/public-eip"
        elif action == "delete":
            method, suffix, body = "DELETE", "", None
        elif action == "reset_key":
            reset_key_id = segment(body["key_id"])
            method, suffix = "PUT", "/api-key/" + reset_key_id + "/reset"
            body = None
        elif action == "auth_flags":
            if not body or any(k not in ("enable_account_sign_up", "enable_anonymous_users") or type(v) is not bool for k,v in body.items()):
                raise McpToolError("MCP_INVALID_ARGS", "Only explicit registration boolean changes supported")
            method, suffix = "PUT", "/auth-config"
        else:
            raise McpToolError("MCP_INVALID_ARGS", "Unsupported mutation")
        notices = ssl_followup(body["enable_ssl"]) if action == "ssl" else {}
        if action == "delete":
            notices = {"warnings":["Deleting this application interrupts its services; PG is retained and may continue to incur charges.",
                                   "Deletion is not automatically reversible; no PG cascade is performed."]}
        if action == "eip":
            notices = {"warnings":["Public connectivity changes may interrupt clients; binding does not prove end-to-end access.",
                                   "EIP charges and release are separate; unbinding does not release the EIP or guarantee billing stops."]}
        if action == "auth_flags":
            notices = {"warnings":["Auth changes may briefly interrupt application functions; prefer a low-traffic window."]}
        if action == "reset_key":
            notices = {
                "warnings":["Existing clients can lose access after the asynchronous reset succeeds."],
                "follow_up":[
                    "After agent success, backend atomically marks the old key deleted and a new key normal.",
                    "Query the job and refresh metadata; key transition does not prove later recovery steps completed.",
                    "Do not use the old key ID to retrieve the new value; correlate the new record before trusted delivery.",
                    "Update downstream credentials through a trusted channel; never return plaintext to the model.",
                ],
                "completion_verified":False,
            }
        digest = self.intent_digest(method, path+suffix, body)
        if not confirm:
            return {"status":"confirmation_required", "application_id":application_id, "action":action, "changes":body, "resource_path":path+suffix, "execution":"not_executed", **notices, **self.plans.issue(digest)}
        if os.getenv("SUPABASE_ENABLE_WRITES") != "true" or os.getenv("HUAWEICLOUD_MCP_READ_ONLY", "false").lower() == "true":
            raise McpToolError("MCP_READ_ONLY", "Writes are disabled")
        # Read the real target immediately before mutation. Unknown/active states fail closed.
        _, target = await self.client.request("GET", path)
        if target.get("id") != application_id or target.get("status") != "normal" or target.get("current_actions"):
            raise McpToolError("MCP_GUARDRAIL_BLOCKED", "Target is not demonstrably ready for mutation")
        from huaweicloud_mcp_core.guardrails import assert_not_protected
        assert_not_protected(target)
        if reset_key_id is not None:
            # Scope the lookup to this application and exact ID. Backend auth remains authoritative.
            _, metadata = await self.client.request("GET", path + "/api-keys",
                                                   query=api_key_query(key_id=reset_key_id))
            try:
                page = key_metadata(metadata)
                records = page["data"]
                ready = (page["total_count"] == 1 and len(records) == 1
                         and records[0].get("id") == reset_key_id
                         and records[0].get("status") == "normal")
            except ValueError:
                ready = False
            if not ready:
                raise McpToolError("MCP_GUARDRAIL_BLOCKED", "Key is not demonstrably normal in this application",
                                   hint="Refresh key metadata and verify its ID and state before resetting.")
        self.plans.claim(plan_id, digest)
        try:
            status, data = await self.client.request(method, path + suffix, body=body)
            result = accepted_job(status, data)
            self.plans.finish(plan_id, "accepted", result["job_id"])
            return {**result, **notices, "plan_id":plan_id}
        except BaseException:
            self.plans.finish(plan_id, "unknown")
            raise RecoveryError("MCP_SDK_ERROR", "Write result unknown", "submission_unknown",
                                "Use inspect_supabase_plan, then query the associated job and resource; do not replay or delete the ledger.", plan_id) from None
