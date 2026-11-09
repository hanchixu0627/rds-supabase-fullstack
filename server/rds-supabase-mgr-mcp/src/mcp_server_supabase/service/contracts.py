"""Pure request validation and conservative asynchronous response normalization.
No transport, credentials, internal endpoints or job terminal-state assumptions.
"""
import re
from typing import Any


def ssl_body(enable_ssl: bool, cert_id: str | None = None) -> dict[str, object]:
    if type(enable_ssl) is not bool:
        raise ValueError('enable_ssl must be boolean')
    if enable_ssl:
        if not isinstance(cert_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{3,64}', cert_id):
            raise ValueError('A valid certificate identifier is required')
    elif cert_id is not None:
        raise ValueError('Certificate must be null when disabling SSL')
    return {'enable_ssl': enable_ssl, 'cert_id': cert_id}


def api_key_query(limit: int = 10, offset: int = 0, status: str | None = None,
                  key_type: str | None = None, sort_key: str = 'created_time',
                  sort_dir: str = 'desc', key_id: str | None = None) -> dict[str, object]:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('limit must be an integer from 1 to 100')
    if type(offset) is not int or offset < 0:
        raise ValueError('offset must be a non-negative integer')
    if status is not None and status not in ('normal', 'creating', 'createfail', 'deleted'):
        raise ValueError('Unsupported status')
    if key_type is not None and key_type not in ('publishable', 'secret', 'anon', 'service_role'):
        raise ValueError('Unsupported key type')
    if sort_key not in ('name','status','type','created_user','updated_user','created_time','updated_time') or sort_dir not in ('asc','desc'):
        raise ValueError('Unsupported sort')
    query: dict[str, object] = {'limit':limit, 'offset':offset, 'sort_key':sort_key, 'sort_dir':sort_dir}
    if status is not None:
        query['status'] = status
    if key_type is not None:
        query['type'] = key_type
    if key_id is not None:
        if not isinstance(key_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', key_id):
            raise ValueError('Invalid key identifier')
        query['id'] = key_id
    return query


def key_metadata(body: dict[str, Any]) -> dict[str, object]:
    """Accept the confirmed list envelope and expose only bounded metadata."""
    rows, total = body.get('data'), body.get('total_count')
    if not isinstance(rows, list) or type(total) is not int or total < len(rows):
        raise ValueError('Unrecognized key metadata envelope')
    allowed = ('id', 'name', 'status', 'type', 'created_time', 'updated_time')
    result = []
    for row in rows[:100]:
        if not isinstance(row, dict):
            raise ValueError('Invalid key metadata record')
        item = {}
        for field in allowed:
            if field not in row:
                continue
            value = row[field]
            if value is not None and type(value) not in (str, int):
                raise ValueError('Invalid key metadata field')
            item[field] = value[:2000] if isinstance(value, str) else value
        result.append(item)
    return {'total_count': total, 'data': result}


def accepted_job(http_status: int, body: dict[str, Any]) -> dict[str, object]:
    job_id = body.get('job_id')
    if http_status != 202 or not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', job_id):
        raise ValueError('Unrecognized acceptance response; reconcile before retrying')
    return {'status':'accepted', 'job_id':job_id, 'complete':False}
