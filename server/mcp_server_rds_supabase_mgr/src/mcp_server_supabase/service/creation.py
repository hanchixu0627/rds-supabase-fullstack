"""Single-mode creation subset from supplied SDK contract; cloud policy stays authoritative."""
import ipaddress
import re
from huaweicloud_mcp_core.errors import McpToolError
from mcp_server_supabase.client.rest import segment
from mcp_server_supabase.service.request_refs import fields,text,validate_request
from mcp_server_supabase.service.network import identifier


def validate_creation(body):
    try:
        required=('name','basic_config','version','mode','flavor_ref','availability_zone','password','storage_component','manage_type')
        fields(body,required+('managed_instance','existing_instance','data_vip','security_group_id'),required)
        text(body['name'],64)
        if len(body['name'])<4 or body['mode']!='Single':raise ValueError()
        if not isinstance(body['version'],str) or not re.fullmatch(r'[1-9]\d*\.(0|[1-9]\d*)\.(0|[1-9]\d*)',body['version']):raise ValueError()
        if not isinstance(body['flavor_ref'],str) or not re.fullmatch(r'rds\.supabase(\.[a-z0-9]+){3,4}',body['flavor_ref']):raise ValueError()
        az=segment(body['availability_zone']);text(body['password'])
        basic=body['basic_config'];fields(basic,('region','vpc_id','subnet_id','time_zone'),('region','vpc_id','subnet_id'))
        for key in ('region','vpc_id','subnet_id'):segment(basic[key])
        if 'time_zone' in basic:text(basic['time_zone'],64)
        if 'data_vip' in body:ipaddress.IPv4Address(body['data_vip'])
        if 'security_group_id' in body:identifier(body['security_group_id'])
        validate_request('storage',body['storage_component'])
        if body['storage_component']['enabled'] and not body['storage_component'].get('sk'):raise ValueError()
        if body['manage_type']=='existed_instance':
            if body.get('managed_instance') is not None:raise ValueError()
            existing=body['existing_instance'];fields(existing,('instance_id','database_name','database_pwd'),('instance_id','database_name','database_pwd'))
            segment(existing['instance_id']);text(existing['database_name']);text(existing['database_pwd'])
        elif body['manage_type']=='newly_instance':
            if body.get('existing_instance') is not None:raise ValueError()
            managed=body['managed_instance']
            required_pg=('datastore','charge_info','flavor_ref','volume','availability_zone','security_group_id','password','enterprise_project_id')
            fields(managed,required_pg+('configuration_id','port','data_vip','tags'),required_pg)
            fields(managed['datastore'],('type','version'),('type','version'))
            if managed['datastore']['type']!='PostgreSQL':raise ValueError()
            text(managed['datastore']['version'],64)
            fields(managed['charge_info'],('charge_mode',),('charge_mode',))
            if managed['charge_info']['charge_mode']!='postPaid':raise ValueError()
            fields(managed['volume'],('type','size'),('type','size'))
            if managed['volume']['type']!='CLOUDSSD' or type(managed['volume']['size']) is not int or managed['volume']['size']<=0:raise ValueError()
            if managed['availability_zone']!=az:raise ValueError()
            text(managed['flavor_ref'],128);text(managed['password']);segment(managed['enterprise_project_id']);identifier(managed['security_group_id'])
            if 'configuration_id' in managed:segment(managed['configuration_id'])
            if 'port' in managed and (type(managed['port']) is not int or not 2100<=managed['port']<=9500):raise ValueError()
            if 'data_vip' in managed:ipaddress.IPv4Address(managed['data_vip'])
            # Tag limits/field policies were referenced but not supplied: do not silently forward.
            if 'tags' in managed:raise ValueError()
        else:raise ValueError()
        return body
    except (ValueError,TypeError,KeyError,McpToolError):
        raise McpToolError('MCP_INVALID_ARGS','Unsupported or invalid Single creation request',
                          hint='Use explicit manage_type, confirmed fields and postPaid for new PG. Backend version, volume, password, quota and flavor policies remain authoritative.') from None
