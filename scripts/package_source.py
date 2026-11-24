"""Package application source only; never include workspaces or installed dependencies."""
from pathlib import Path
import zipfile
import hashlib
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'.artifacts/ResearchHub-0.1.0-source.zip'
INCLUDE=['backend','frontend/src','frontend/tests','frontend/scripts','frontend/index.html','frontend/package.json','frontend/package-lock.json','frontend/tsconfig.json','frontend/vite.config.ts','schemas','examples','scripts','docs','README.md','AGENTS.md','DEVELOPMENT_STATUS.md','pytest.ini','.gitignore']
if __name__=='__main__':
    OUTPUT.parent.mkdir(exist_ok=True)
    paths=set()
    for name in INCLUDE:
        source=ROOT/name
        paths.update([source] if source.is_file() else source.rglob('*'))
    with zipfile.ZipFile(OUTPUT,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(paths):
            relative=path.relative_to(ROOT)
            if path.is_file() and not {'__pycache__','.pytest_cache','node_modules','dist'} & set(relative.parts) and path.suffix not in {'.pyc','.tsbuildinfo','.db','.sqlite3','.zip','.pdf','.log'}:
                z.write(path,relative.as_posix())
    with zipfile.ZipFile(OUTPUT) as z:
        assert z.testzip() is None
        count=len(z.namelist())
    print(f'{OUTPUT}\n{count} files\nSHA256 {hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}')
