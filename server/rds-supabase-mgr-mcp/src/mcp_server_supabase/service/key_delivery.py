"""Deliver an explicitly selected key to an operator-owned local file, never to MCP output."""
import os
import stat
from pathlib import Path
from huaweicloud_mcp_core.errors import McpToolError
from huaweicloud_mcp_core.guardrails import assert_not_protected
from mcp_server_supabase.client.rest import segment
from mcp_server_supabase.failures import RecoveryError
from mcp_server_supabase.service.contracts import api_key_query,key_metadata
from mcp_server_supabase.service.request_refs import load_request,fields


def destination(alias):
    try:
        request=load_request(alias);fields(request,('output_file',),('output_file',))
        path=Path(request['output_file'])
        if not path.is_absolute() or path.exists() or path.is_symlink() or path.parent.resolve()!=path.parent:raise ValueError()
        meta=path.parent.stat()
        if not stat.S_ISDIR(meta.st_mode):raise ValueError()
        if os.name!='nt' and (meta.st_uid!=os.getuid() or meta.st_mode & 0o077):raise ValueError()
        return path
    except (OSError,ValueError,TypeError,KeyError):
        raise McpToolError('MCP_INVALID_ARGS','Configure a new output file in a protected operator-owned directory') from None

async def deliver(service,application_id,key_id,delivery_ref,confirm=False,plan_id=None):
    path=destination(delivery_ref)
    route=service.app(application_id)+'/api-key/'+segment(key_id)+'/value'
    digest=service.intent_digest('GET',route,{'output_file':str(path)})
    if not confirm:
        return {'status':'confirmation_required','execution':'not_executed','application_id':application_id,
                'key_id':key_id,'delivery_ref':delivery_ref,'warnings':['This operation fetches a plaintext key into a local file. Only the trusted operator may open/copy it; never return its contents to the model.'],**service.plans.issue(digest)}
    if os.getenv('SUPABASE_ENABLE_WRITES')!='true' or os.getenv('HUAWEICLOUD_MCP_READ_ONLY','false').lower()=='true':
        raise McpToolError('MCP_READ_ONLY','Sensitive local delivery requires explicit write permission')
    _,target=await service.client.request('GET',service.app(application_id))
    if not isinstance(target,dict) or target.get('id')!=application_id or target.get('status')!='normal' or target.get('current_actions'):
        raise McpToolError('MCP_GUARDRAIL_BLOCKED','Application not ready')
    assert_not_protected(target)
    _,raw=await service.client.request('GET',service.app(application_id)+'/api-keys',query=api_key_query(key_id=key_id))
    try:
        page=key_metadata(raw)
        if page['total_count']!=1 or len(page['data'])!=1 or page['data'][0].get('id')!=key_id or page['data'][0].get('status')!='normal':raise ValueError()
    except (ValueError,TypeError):
        raise McpToolError('MCP_GUARDRAIL_BLOCKED','Key identity and state not verified') from None
    service.plans.claim(plan_id,digest)
    descriptor=None
    try:
        # Reserve before fetching. Never overwrite a file that appeared after preview.
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        status,response=await service.client.request('GET',route)
        value=response.get('api_key')
        if status!=200 or not isinstance(value,str) or not value or len(value)>65536:raise ValueError()
        with os.fdopen(descriptor,'w',encoding='utf-8') as handle:
            descriptor=None
            handle.write(value);handle.flush();os.fsync(handle.fileno())
        service.plans.finish(plan_id,'accepted')
        return {'status':'delivered_locally','plan_id':plan_id,'delivery_ref':delivery_ref,
                'plaintext_returned':False,'cloud_writes_performed':False,'business_verified':False}
    except BaseException:
        service.plans.finish(plan_id,'unknown')
        raise RecoveryError('MCP_SDK_ERROR','Local key delivery result unknown','submission_unknown',
                            'Ask the trusted operator to inspect the protected destination; do not fetch again or expose file contents to the model.',plan_id) from None
    finally:
        if descriptor is not None:os.close(descriptor)
