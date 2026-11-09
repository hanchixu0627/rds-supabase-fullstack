"""Install the local read-only Claude workspace. No business cloud calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

VERSION = 'local-client-0.1.0-dev'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def offline_env():
    env = {k:v for k,v in os.environ.items() if not k.startswith(('HUAWEICLOUD_', 'SUPABASE_')) and k not in ('PYTHONPATH','PYTHONHOME')}
    env.update(HUAWEICLOUD_MCP_READ_ONLY='true', SUPABASE_ENABLE_WRITES='false', SUPABASE_TRANSPORT='sdk_core')
    return env

def setup(bundle, root, python, uv, execute=subprocess.run):
    workspace = root / 'workspace'
    config_file = workspace / '.mcp.json'
    skill = workspace / '.claude' / 'skills' / 'huaweicloud-supabase'
    marker = root / 'installed.json'
    if marker.exists():
        saved = json.loads(marker.read_text(encoding='utf-8'))
        if saved.get('version') != VERSION:
            raise ValueError('Different client version installed; preserve state and review migration.')
        for relative, sha in saved['files'].items():
            p = workspace / relative
            if not p.is_file() or p.is_symlink() or digest(p) != sha:
                raise ValueError('Installed configuration or Skill changed/missing; preserve it and review before restart.')
        return {'config': json.loads(config_file.read_text(encoding='utf-8')), 'reused': True}
    if config_file.exists() or skill.exists():
        raise ValueError('Existing workspace configuration or Skill: refusing to overwrite.')
    env = offline_env()
    execute([str(uv), '--no-config', 'pip', 'install', '--offline', '--no-index', '--find-links', str(bundle/'wheels'),
             '--python', str(python), '-r', str(bundle/'requirements-development.txt'),
             'huaweicloud-mcp-core==1.0.0', 'mcp_server_supabase==0.3.8a2'], check=True, env=env)
    execute([str(uv), '--no-config', 'pip', 'check', '--python', str(python)], check=True, env=env)
    execute([str(python), '-I', '-m', 'mcp_server_supabase.diagnostics', 'offline'], check=True, env=env)
    state = root / 'state' / 'plans.sqlite3'
    state.parent.mkdir(parents=True, exist_ok=True)
    config = {'mcpServers': {'huaweicloud-supabase': {
        'command': str(python), 'args': ['-I','-m', 'mcp_server_supabase.main'],
        'env': {'SUPABASE_TRANSPORT':'sdk_core', 'HUAWEICLOUD_MCP_READ_ONLY':'true',
                'SUPABASE_ENABLE_WRITES':'false', 'SUPABASE_STATE_FILE':str(state)}}}}
    workspace.mkdir(parents=True, exist_ok=True)
    # No activation until dependency check and offline diagnostic both pass.
    shutil.copytree(bundle/'skill', skill)
    try:
        with config_file.open('x', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        files = {p.relative_to(workspace).as_posix():digest(p) for p in skill.rglob('*') if p.is_file()}
        files['.mcp.json'] = digest(config_file)
        with marker.open('x', encoding='utf-8') as f:
            json.dump({'version': VERSION,'files':files},f,indent=2)
    except Exception:
        # Retain installation evidence; never delete a ledger or overwrite files on retry.
        raise
    return {'config':config, 'reused':False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    result=setup(args.bundle.resolve(),args.root.resolve(),args.root.resolve()/'runtime'/'Scripts'/'python.exe',args.bundle.resolve()/'uv.exe')
    print(json.dumps({'installed':True,'reused':result['reused'],'cloud_called':False}))
