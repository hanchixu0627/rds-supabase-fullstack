"""Product recovery metadata; never infer write safety from an HTTP error."""
from huaweicloud_mcp_core.errors import McpToolError


class RecoveryError(McpToolError):
    def __init__(self, code, message, category, next_action, plan_id=None):
        super().__init__(code, message, hint=next_action)
        self.recovery = {'category':category, 'next_action':next_action, 'automatic_retry':False}
        if plan_id is not None:
            self.recovery['plan_id'] = plan_id

    def to_dict(self):
        result = super().to_dict()
        result['error']['recovery'] = dict(self.recovery)
        return result


def http_failure(status):
    code, category, action = {
        400: ('MCP_INVALID_ARGS','invalid_request','Check the input contract; review a new plan before a changed write.'),
        401: ('MCP_PERMISSION_DENIED','authentication','Have the operator verify the configured identity; do not ask for credentials in chat.'),
        403: ('MCP_PERMISSION_DENIED','permission','Ask the administrator to check target permissions; do not switch identities automatically.'),
        404: ('MCP_NOT_FOUND','not_found','Recheck the target and endpoint; absence alone does not prove deletion succeeded.'),
        409: ('MCP_GUARDRAIL_BLOCKED','state_conflict','Refresh resource state before proposing another operation.'),
        429: ('MCP_SDK_ERROR','rate_limited','Pause queries and retry a read only under a bounded policy; reconcile any submitted write.'),
    }.get(status, ('MCP_SDK_ERROR','service_unavailable' if status >= 500 else 'unexpected_http',
                   'Check service availability and the API contract; reconcile any submitted write before retrying.'))
    return RecoveryError(code, f'API returned HTTP {status}', category, action)
