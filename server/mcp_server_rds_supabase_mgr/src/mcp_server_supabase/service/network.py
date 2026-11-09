"""Native VPC v3 operations; independent endpoint, ledger and response contracts."""
import ipaddress
import os
import re
import uuid
from huaweicloud_mcp_core.errors import McpToolError
from huaweicloud_mcp_core.guardrails import assert_not_protected
from mcp_server_supabase.client.sdk_core import configured_client
from mcp_server_supabase.failures import RecoveryError
from mcp_server_supabase.service.operations import Operations, safe

ROOT='/v3/{project}/vpc/'

def identifier(value):
    try:
        if not isinstance(value,str) or str(uuid.UUID(value))!=value:raise ValueError()
    except (ValueError,AttributeError):
        raise McpToolError('MCP_INVALID_ARGS','A canonical VPC resource UUID is required') from None
    return value

class Network(Operations):
    def __init__(self,client=None,plans=None):
        if client is None:
            client=configured_client()
            # Never silently send a VPC request to the RDS endpoint.
            client.endpoint=os.getenv('SUPABASE_VPC_ENDPOINT','')
        super().__init__(client,plans)

    async def list_groups(self,limit=10,marker=None):
        if type(limit) is not int or not 1<=limit<=100:
            raise McpToolError('MCP_INVALID_ARGS','Use limit 1-100')
        query={'limit':limit}
        if marker is not None:query['marker']=identifier(marker)
        _,data=await self.client.request('GET',ROOT+'security-groups',query=query)
        return {'data':safe(data),'note':'One bounded page; follow the service pagination marker.'}

    async def show_group(self,group_id):
        _,data=await self.client.request('GET',ROOT+'security-groups/'+identifier(group_id))
        group=data.get('security_group') if isinstance(data,dict) else None
        if not isinstance(group,dict) or group.get('id')!=group_id:
            raise McpToolError('MCP_SDK_ERROR','Security group identity not verified')
        return {'data':safe(group)}

    async def create_group(self,name,confirm=False,plan_id=None):
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',name):
            raise McpToolError('MCP_INVALID_ARGS','Use a 1-64 character ASCII group name with letters, digits, underscore, dot or hyphen')
        return await self._change('POST','security-groups',{'security_group':{'name':name}},confirm,plan_id,'security_group')

    async def add_rule(self,group_id,source_cidr,port=8443,confirm=False,plan_id=None):
        identifier(group_id)
        try:
            source=ipaddress.ip_network(source_cidr,strict=True)
            if source.prefixlen==0 or type(port) is not int or not 1<=port<=65535:raise ValueError()
        except (ValueError,TypeError):
            raise McpToolError('MCP_INVALID_ARGS','Specify a bounded canonical source CIDR and port 1-65535; world-wide ingress is unsupported') from None
        rule={'security_group_id':group_id,'direction':'ingress','ethertype':'IPv4' if source.version==4 else 'IPv6',
              'protocol':'tcp','multiport':str(port),'remote_ip_prefix':str(source),'action':'allow','priority':1}
        return await self._change('POST','security-group-rules',{'security_group_rule':rule},confirm,plan_id,'security_group_rule',group_id)

    async def delete_rule(self,group_id,rule_id,confirm=False,plan_id=None):
        identifier(group_id);identifier(rule_id)
        return await self._change('DELETE','security-group-rules/'+rule_id,None,confirm,plan_id,None,group_id,rule_id)

    async def _change(self,method,suffix,body,confirm,plan_id,result_key,group_id=None,rule_id=None):
        path=ROOT+suffix
        # Bind the selected parent even for DELETE whose URL only carries the rule ID.
        digest=self.intent_digest(method,path,{'request':body,'group_id':group_id})
        notices={'warnings':['Shared security-group changes affect every associated resource; verify the association inventory before confirming.',
                             'Creating a group does not attach it to an application or open port 8443.'],
                 'completion_verified':False}
        if not confirm:
            return {'status':'confirmation_required','execution':'not_executed','changes':body,'group_id':group_id,
                    'resource_path':path,**notices,**self.plans.issue(digest)}
        if os.getenv('SUPABASE_ENABLE_WRITES')!='true' or os.getenv('HUAWEICLOUD_MCP_READ_ONLY','false').lower()=='true':
            raise McpToolError('MCP_READ_ONLY','Writes are disabled')
        if rule_id:
            _,data=await self.client.request('GET',path)
            rule=data.get('security_group_rule') if isinstance(data,dict) else None
            if not isinstance(rule,dict) or rule.get('id')!=rule_id or rule.get('security_group_id')!=group_id:
                raise McpToolError('MCP_GUARDRAIL_BLOCKED','Rule ownership not verified')
        if group_id:
            _,data=await self.client.request('GET',ROOT+'security-groups/'+group_id)
            group=data.get('security_group') if isinstance(data,dict) else None
            if not isinstance(group,dict) or group.get('id')!=group_id:
                raise McpToolError('MCP_GUARDRAIL_BLOCKED','Group identity not verified')
            assert_not_protected(group)
            if method=='POST':
                existing=group.get('security_group_rules')
                requested=body['security_group_rule']
                if not isinstance(existing,list):
                    raise McpToolError('MCP_GUARDRAIL_BLOCKED','Existing rules must be read before adding ingress')
                if any(isinstance(r,dict) and all(r.get(k)==v for k,v in requested.items() if k!='security_group_id') for r in existing):
                    raise McpToolError('MCP_GUARDRAIL_BLOCKED','An identical rule already exists')
        self.plans.claim(plan_id,digest)
        try:
            status,data=await self.client.request(method,path,body=body)
            resource_id=rule_id
            if method=='DELETE':
                if status!=204:raise ValueError()
            else:
                record=data.get(result_key)
                if status!=201 or not isinstance(record,dict):raise ValueError()
                resource_id=identifier(record.get('id'))
                if group_id and record.get('security_group_id')!=group_id:raise ValueError()
            self.plans.finish(plan_id,'accepted')
            return {'status':'applied','resource_id':resource_id,'plan_id':plan_id,**notices,
                    'follow_up':'Read the resource and verify application connectivity. No RDS job is created. This ledger record remains non-replayable.'}
        except BaseException:
            self.plans.finish(plan_id,'unknown')
            raise RecoveryError('MCP_SDK_ERROR','VPC write result unknown','submission_unknown',
                                'Inspect the plan and VPC resource; never blindly repeat a write.',plan_id) from None
