"""Build from tracked release inputs only, never from the surrounding workspace."""
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
archive = root / 'dist/adaptive-study-center-workbuddy.zip'
archive.parent.mkdir(exist_ok=True)
with ZipFile(archive, 'w') as bundle:
    for name in sorted(filter(None, paths)):
        if name not in {'SKILL.md', 'LICENSE'} and not name.startswith(('agents/', 'assets/', 'examples/', 'references/', 'scripts/inspect_bundle.py')):
            continue
        data = (root / name).read_bytes()
        if not name.endswith('.png'):
            data = data.replace(b'\r\n', b'\n')
        bundle.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
