#!/usr/bin/env python3
"""Remove only known retired files after installing the full v1.7.9.1 package.
Dry run by default. A modified file, symlink or unrelated file is never removed.
Usage: python qa/cleanup_retired.py . [--apply]
"""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, sys

def validate_root(root: Path) -> None:
    release=json.loads((root/'release.json').read_text(encoding='utf-8'))
    if release.get('version')!='1.7.9.1' or not (root/'index.html').is_file():
        raise ValueError('Install the full 1.7.9.1 package in this folder first.')

def inspect_entry(root: Path, entry: dict) -> tuple[str, Path | None]:
    rel=PurePosixPath(entry['path'])
    if rel.is_absolute() or '..' in rel.parts or not rel.parts or '\\' in entry['path']:
        return 'unsafe-path',None
    path=root.joinpath(*rel.parts)
    # Do not follow links, including a symlink in a parent directory.
    current=root
    for part in rel.parts:
        current=current/part
        if current.is_symlink():return 'unsafe-symlink',path
    if not path.resolve().is_relative_to(root.resolve()):return 'unsafe-path',None
    if not path.exists():return 'already-absent',path
    if not path.is_file():return 'not-a-file',path
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    return ('retired-unchanged' if sha in entry.get('sha256',[]) else 'modified-keep'),path

def clean(root: Path, entries: list[dict], apply: bool=False) -> list[dict]:
    validate_root(root)
    results=[]
    for entry in entries:
        status,path=inspect_entry(root,entry)
        if status=='retired-unchanged' and apply:
            # Recheck immediately before removing anything.
            status,path=inspect_entry(root,entry)
            if status=='retired-unchanged':path.unlink();status='removed'
        results.append({'path':entry['path'],'status':status})
    return results

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',nargs='?',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--apply',action='store_true',help='Delete only matching known retired files.')
    args=parser.parse_args();root=args.root.resolve()
    try:
        inventory=json.loads((Path(__file__).parent/'retired-files.json').read_text(encoding='utf-8'))
        results=clean(root,inventory['files'],args.apply)
    except (OSError,ValueError,KeyError) as exc:
        print(f'Cleanup stopped: {exc}',file=sys.stderr);return 2
    print('APPLIED' if args.apply else 'DRY RUN — no files changed')
    for row in results:
        if row['status']!='already-absent':print(row['status'].upper(),row['path'])
    print(json.dumps({s:sum(r['status']==s for r in results) for s in sorted({r['status'] for r in results})},indent=2))
    return 1 if any(r['status'] in {'unsafe-path','unsafe-symlink','not-a-file','modified-keep'} for r in results) else 0
if __name__=='__main__':raise SystemExit(main())
