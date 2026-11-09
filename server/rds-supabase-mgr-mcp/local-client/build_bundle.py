"""Build from the pinned public delivery plus pinned official uv wheel. No npm."""
import argparse, hashlib, io, json, shutil, urllib.request, zipfile
from pathlib import Path
UV_URL='https://files.pythonhosted.org/packages/8e/4f/041b59d2a38807a3e31ef41064cf3e45d2752fe0409d89040d52778049ae/uv-0.13.7-py3-none-win_amd64.whl'
UV_SHA='2835e2ab397d0db86323b9975dce75ecd76aa9cfa0d6a2aea84734aae7f8c9b3'
MANIFEST_SHA='b766dbd405e63d05086d846232dc1b12dbf0ce10440531f576c499959d4c3565'
def sha(b):return hashlib.sha256(b).hexdigest()
def build(source, output):
    manifest=source/'SHA256SUMS.txt'
    if sha(manifest.read_bytes())!=MANIFEST_SHA:raise ValueError('Not the pinned 0.3.8a2 delivery')
    if output.exists():raise ValueError('Use a new build directory')
    output.mkdir(parents=True)
    allowed={'requirements-development.txt','LICENSE','BLOCKERS.md'}
    for line in manifest.read_text().splitlines():
        digest,name=line.split('  ',1)
        p=source/name
        if p.is_symlink() or source not in p.resolve().parents or sha(p.read_bytes())!=digest:raise ValueError('Invalid source payload')
        if name in allowed or name.startswith(('wheels/','skill/')):
            dest=output/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    data=urllib.request.urlopen(UV_URL,timeout=90).read()
    if sha(data)!=UV_SHA:raise ValueError('uv download hash mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as wheel:
        exe=[n for n in wheel.namelist() if n.endswith('/uv.exe')]
        if len(exe)!=1:raise ValueError('Unexpected uv wheel')
        (output/'uv.exe').write_bytes(wheel.read(exe[0]))
        for name in wheel.namelist():
            if '.dist-info/licenses/' in name and not name.endswith('/'):
                dest=output/'licenses'/'uv'/name.split('.dist-info/licenses/',1)[1]
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(wheel.read(name))
    here=Path(__file__).resolve().parent
    for name in ['setup_client.py','start-supabase.ps1','README.md']:
        shutil.copyfile(here/name,output/name)
    (output/'PROVENANCE.json').write_text(json.dumps({'mcp_version':'0.3.8a2','client_version':'0.1.0-dev','uv_version':'0.13.7','uv_url':UV_URL,'uv_wheel_sha256':UV_SHA,'python_requested':'3.12.10','windows_e2e':'not_performed'},indent=2))
    checks={p.relative_to(output).as_posix():sha(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file()}
    (output/'DELIVERY.json').write_text(json.dumps(checks,indent=2))
    archive=Path(str(output)+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(output.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(output).as_posix())
    Path(str(archive)+'.sha256.txt').write_text(sha(archive.read_bytes())+'  '+archive.name+'\n')
    print(archive)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    a=parser.parse_args();build(a.source.resolve(),a.output.resolve())
