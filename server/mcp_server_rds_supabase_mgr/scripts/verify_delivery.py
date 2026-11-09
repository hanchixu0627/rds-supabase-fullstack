"""Standard-library pre-install check. No network, credentials or cloud calls."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import struct
import sys


def target_match(system, machine, python, bits):
    return system == 'win32' and machine.lower() in ('amd64','x86_64') and tuple(python[:2]) == (3,12) and bits == 64


def verify_files(root):
    root=Path(root).resolve()
    seen=set()
    for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1)
        relative=PurePosixPath(name)
        if not re.fullmatch('[0-9a-f]{64}',digest) or relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name or name in seen:
            raise ValueError('Invalid manifest entry')
        seen.add(name)
        file=root.joinpath(*relative.parts)
        if file.is_symlink() or root not in file.resolve().parents or not file.is_file():
            raise ValueError('Missing or unsafe delivery file')
        if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
            raise ValueError('Delivery checksum mismatch')
    if not seen:
        raise ValueError('Empty manifest')
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt'}
    if actual != seen:
        raise ValueError('Unexpected or unlisted delivery files; use a fresh extraction directory')
    return len(seen)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    report={'system':sys.platform,'machine':platform.machine(),'python':platform.python_version(),
            'bits':struct.calcsize('P')*8,'network_attempted':False,'windows_acceptance':'not_performed'}
    report['target_match']=target_match(sys.platform,platform.machine(),sys.version_info,report['bits'])
    try:
        report['verified_files']=verify_files(args.bundle)
        report['checksums_valid']=True
    except (OSError,ValueError):
        report['checksums_valid']=False
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['target_match'] and report['checksums_valid'] else 2

if __name__=='__main__':
    sys.exit(main())
