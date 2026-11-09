"""Operator-managed local request aliases. Secret values never become tool inputs."""
import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit
from huaweicloud_mcp_core.errors import McpToolError


def load_request(alias):
    try:
        if not isinstance(alias,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',alias):raise ValueError()
        configured=os.environ.get('SUPABASE_REQUESTS_FILE','')
        path=Path(configured)
        if not configured or not path.is_absolute() or path.is_symlink():raise ValueError()
        flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)
        with os.fdopen(os.open(path,flags),'r',encoding='utf-8') as handle:
            meta=os.fstat(handle.fileno())
            if not stat.S_ISREG(meta.st_mode) or meta.st_size>65536:raise ValueError()
            if os.name!='nt' and (meta.st_uid!=os.getuid() or meta.st_mode & 0o077):raise ValueError()
            raw=handle.read(65537)
        if len(raw)>65536:raise ValueError()
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError()
                result[key]=value
            return result
        registry=json.loads(raw,object_pairs_hook=unique)
        body=registry[alias]
        if not isinstance(body,dict):raise ValueError()
        return body
    except Exception:
        raise McpToolError('MCP_INVALID_ARGS','Local request reference unavailable or unsafe',
                           hint='Ask the operator to configure a protected request registry; never paste secrets into chat.') from None


def fields(value, allowed, required=()):
    if not isinstance(value,dict) or set(value)-set(allowed) or not set(required)<=set(value):raise ValueError()


def text(value, limit=2048):
    if not isinstance(value,str) or not value or len(value)>limit or any(ord(c)<32 for c in value):raise ValueError()


def boolean(value):
    if type(value) is not bool:raise ValueError()


def url(value):
    text(value)
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:raise ValueError()


def validate_request(action, body):
    try:
        if action=='password':
            fields(body,('application_password',),('application_password',));text(body['application_password'])
        elif action=='storage':
            fields(body,('enabled','type','bucket_name','ak','sk'),('enabled',));boolean(body['enabled'])
            if 'type' in body and body['type']!='obs':raise ValueError()
            if body['enabled']:
                patterns={'bucket_name':r'[a-zA-Z0-9.\-]{3,64}','ak':r'[a-zA-Z0-9_-]{1,32}','sk':r'[a-zA-Z0-9_-]{1,64}'}
                for key,pattern in patterns.items():
                    if key=='sk' and key not in body:continue
                    if not isinstance(body.get(key),str) or not re.fullmatch(pattern,body[key]):raise ValueError()
            elif any(body.get(k) not in (None,'') for k in ('bucket_name','ak','sk')):raise ValueError()
        elif action=='auth_config':
            fields(body,('enable_account_sign_up','enable_anonymous_users','api_external_url','site_url','allow_redirect_urls','github_oauth_provider','email_oauth_provider','email_template_config'))
            if not body or any(v is None for v in body.values()):raise ValueError()
            for key in ('enable_account_sign_up','enable_anonymous_users'):
                if key in body:boolean(body[key])
            for key in ('api_external_url','site_url'):
                if key in body:url(body[key])
            if 'allow_redirect_urls' in body:
                text(body['allow_redirect_urls'])
                values=body['allow_redirect_urls'].split(',')
                if len(values)>10:raise ValueError()
                for value in values:url(value)
            if 'github_oauth_provider' in body:
                provider=body['github_oauth_provider']
                fields(provider,('enable_github','oauth_client_id','oauth_client_secret','redirect_uri'))
                if not provider:raise ValueError()
                if 'enable_github' in provider:
                    boolean(provider['enable_github'])
                    if not provider['enable_github'] and set(provider)!={'enable_github'}:raise ValueError()
                for key in ('oauth_client_id','oauth_client_secret'):
                    if key in provider:text(provider[key])
                if 'redirect_uri' in provider:url(provider['redirect_uri'])
            if 'email_oauth_provider' in body:
                provider=body['email_oauth_provider']
                fields(provider,('enable_email_sign_up','enable_email_auto_confirm','smtp_config'))
                if not provider:raise ValueError()
                for key in ('enable_email_sign_up','enable_email_auto_confirm'):
                    if key in provider:boolean(provider[key])
                if provider.get('enable_email_sign_up') is False and set(provider)!={'enable_email_sign_up'}:raise ValueError()
                if 'smtp_config' in provider:
                    smtp=provider['smtp_config']
                    fields(smtp,('smtp_host','smtp_port','smtp_user','smtp_pwd','smtp_admin_email','smtp_sender_name','smtp_max_frequency'))
                    if not smtp:raise ValueError()
                    for key,value in smtp.items():
                        if key=='smtp_port':
                            if type(value) is not int or not 1<=value<=65535:raise ValueError()
                        elif key=='smtp_max_frequency':
                            if type(value) is not int or value<0:raise ValueError()
                        else:text(value)
            if 'email_template_config' in body:
                templates=body['email_template_config']
                # Only this template identifier is established by the supplied contract.
                fields(templates,('mailer_confirmation',),('mailer_confirmation',))
                fields(templates['mailer_confirmation'],('subject','url'))
                if not templates['mailer_confirmation']:raise ValueError()
                for key,value in templates['mailer_confirmation'].items():
                    if key=='url':url(value)
                    else:text(value)
        else:raise ValueError()
        return body
    except (ValueError,TypeError,KeyError):
        raise McpToolError('MCP_INVALID_ARGS','Unsupported or invalid referenced request fields',
                          hint='Use the documented operation schema; unknown fields and ambiguous clear operations are rejected.') from None


def preview_request(body):
    hidden={'application_password','password','database_pwd','smtp_pwd','oauth_client_secret','ak','sk'}
    def scrub(value):
        if isinstance(value,dict):return {k:('[configured locally]' if k in hidden else scrub(v)) for k,v in value.items()}
        if isinstance(value,list):return [scrub(v) for v in value]
        # Query strings may contain signed tokens. Do not echo them in previews.
        if isinstance(value,str) and value.startswith(('https://','http://')):
            parsed=urlsplit(value)
            return parsed._replace(query='[redacted]' if parsed.query else '').geturl()
        return value
    return scrub(body)
