"""Verified request-body subset; no assumption about native VPC endpoint mapping."""
import ipaddress
import uuid


def ingress_rule(security_group_id: str, source_cidr: str, port: int = 8443) -> dict:
    try:
        group = str(uuid.UUID(security_group_id))
        network = ipaddress.ip_network(source_cidr, strict=True)
    except (ValueError, TypeError, AttributeError):
        raise ValueError('A security group UUID and explicit network CIDR are required') from None
    if network.prefixlen == 0:
        raise ValueError('Unrestricted ingress is not supported by this helper')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Port must be an integer from 1 to 65535')
    return {'security_group_rules':[{
        'direction':'ingress', 'security_group_id':group, 'description':'',
        'ethertype':'IPv4' if network.version == 4 else 'IPv6',
        'protocol':'TCP', 'multiport':str(port), 'remote_ip_prefix':str(network),
        'action':'allow', 'priority':'1',
    }]}


def ssl_followup(enabled: bool) -> dict:
    return {
        'target_protocol':'https' if enabled else 'http',
        'warnings':['Application functions may be briefly unavailable. Prefer a low-traffic change window.',
                    'After SSL completes, review affected Auth URLs manually; incompatible protocols can break authentication.'],
        'follow_up':[
            'Verify the SSL job and application state before adjusting dependent settings.',
            'Review site_url, api_external_url and allow_redirect_urls where they reference this application.',
            'If GitHub OAuth is enabled, review its redirect_uri and provider callback configuration.',
            'If email authentication or Storage-hosted email templates are used, review the relevant template URLs.',
            'Do not rewrite unrelated URLs or SMTP host automatically; verify login after manual changes.',
        ],
        'urls_automatically_modified':False,
    }
