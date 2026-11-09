"""Workstation checks and explicitly opted-in read-only MCP integration.

Never accepts credentials on the command line or exposes cloud response values.
"""
import argparse
import asyncio
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit


def configuration_report():
    checks = {'python_supported': sys.version_info >= (3, 10)}
    packages = {}
    for package in ('mcp', 'huaweicloud-mcp-core', 'mcp_server_supabase', 'huaweicloudsdkcore'):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    checks['dependencies_present'] = all(packages.values())
    try:
        url = urlsplit(os.getenv('SUPABASE_RDS_ENDPOINT', ''))
        checks['endpoint_valid'] = bool(url.scheme == 'https' and url.hostname and
            not url.username and not url.password and not url.query and not url.fragment
            and url.path in ('', '/') and (url.port is None or 1 <= url.port <= 65535))
    except ValueError:
        checks['endpoint_valid'] = False
    checks['project_valid'] = bool(re.fullmatch(r'[A-Za-z0-9_-]{1,128}', os.getenv('HUAWEICLOUD_PROJECT_ID','')))
    transport = os.getenv('SUPABASE_TRANSPORT', 'rest')
    checks['transport_valid'] = transport in ('rest', 'sdk_core')
    if transport == 'sdk_core':
        ak, sk, sts = (os.getenv(key, '') for key in
            ('HUAWEICLOUD_ACCESS_KEY', 'HUAWEICLOUD_SECRET_KEY', 'HUAWEICLOUD_SECURITY_TOKEN'))
        checks['sdk_credentials_present_and_valid'] = bool(ak and sk and
            all('\r' not in value and '\n' not in value for value in (ak, sk, sts)))
    else:
        token = os.getenv('HUAWEICLOUD_AUTH_TOKEN', '')
        checks['token_present_and_valid'] = bool(token and '\r' not in token and '\n' not in token)
    return {'mode':'check', 'checks':checks, 'packages':packages,
            'cloud_ready':all(checks.values()), 'network_attempted':False,
            'note':'Configuration syntax only; network, permissions and server identity are not verified.'}


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


async def protocol_report(mode, application_id=None, job_id=None):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    offline = mode == 'offline'
    checks = []
    with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as errors:
        env = dict(os.environ)
        if offline:
            env = {k:v for k,v in env.items() if not k.startswith(('HUAWEICLOUD_', 'SUPABASE_'))}
        env.update({'SUPABASE_ENABLE_WRITES':'false',
                    'HUAWEICLOUD_MCP_READ_ONLY':'false' if offline else 'true',
                    'SUPABASE_STATE_FILE':str(Path(directory)/'plans.db')})
        params = StdioServerParameters(command=sys.executable,
            args=['-m','mcp_server_supabase.main'],env=env)
        async with stdio_client(params,errlog=errors) as (read, write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                checks.append({'check':'tool_discovery','passed':{'get_supabase_capabilities',
                    'plan_supabase_creation','cancel_supabase_plan','list_supabase_api_keys','wait_supabase_job','reconcile_supabase_auth_plan'} <= names})
                async def call(name, args, predicate=None):
                    result = await session.call_tool(name,args)
                    data = payload(result)
                    passed = not result.is_error and isinstance(data,dict) and 'error' not in data
                    if passed and predicate is not None:
                        passed = bool(predicate(data))
                    checks.append({'check':name,'passed':passed})
                    return data if passed else {}
                await call('get_supabase_capabilities',{},lambda d:d.get('cloud_verified') is False)
                if offline:
                    await call('plan_supabase_creation',{'manage_type':'newly_instance'},
                               lambda d:d.get('execution')=='not_executed')
                    await call('plan_supabase_ssl',{'enable_ssl':True},lambda d:d.get('execution')=='not_executed')
                    preview = await call('change_supabase_ssl',{'application_id':'offline-fixture','enable_ssl':False},
                                         lambda d:d.get('status')=='confirmation_required' and bool(d.get('plan_id')))
                    if preview:
                        await call('cancel_supabase_plan',{'plan_id':preview['plan_id']},
                                   lambda d:d.get('state')=='cancelled' and d.get('cloud_cancellation_requested') is False)
                else:
                    await call('list_supabase_applications',{'limit':1})
                    if application_id:
                        await call('show_supabase_application',{'application_id':application_id})
                        await call('list_supabase_api_keys',{'application_id':application_id,'limit':1})
                    if job_id:
                        await call('show_supabase_job',{'job_id':job_id})
    return {'mode':mode,'passed':all(check['passed'] for check in checks),'checks':checks,
            'network_attempted':not offline,'cloud_writes_enabled':False,
            'completion_verified':False,
            'note':'Response values are omitted. Read success is not task completion or production acceptance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('check','offline','readonly'))
    parser.add_argument('--allow-cloud-read',action='store_true')
    parser.add_argument('--application-id')
    parser.add_argument('--job-id')
    args = parser.parse_args()
    report = {'mode':args.mode,'passed':False,'network_attempted':False}
    try:
        if args.mode == 'check':
            report = configuration_report()
            code = 0 if report['cloud_ready'] else 2
        elif args.mode == 'readonly' and not args.allow_cloud_read:
            report['error'] = 'Cloud reads require --allow-cloud-read and an authorized test identity.'
            code = 2
        elif args.mode == 'readonly' and not configuration_report()['cloud_ready']:
            report['error'] = 'Configuration incomplete; run check first.'
            code = 2
        else:
            # Conservative on connection failures: a cloud read may already have run.
            report['network_attempted'] = args.mode == 'readonly'
            report = asyncio.run(protocol_report(args.mode,args.application_id,args.job_id))
            code = 0 if report['passed'] else 1
    except Exception:
        report['error'] = 'Diagnostic failed; inspect the local installation and service configuration.'
        code = 1
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
