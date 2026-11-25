# PyInstaller onedir; only explicit application resources enter the distribution.
from pathlib import Path
root=Path(SPECPATH).parent
a=Analysis([str(root/'backend/desktop_entry.py')],pathex=[str(root/'backend')],
 datas=[(str(root/'backend/migrations'),'migrations'),(str(root/'frontend/dist'),'frontend/dist')],
 hiddenimports=['uvicorn.logging','uvicorn.loops.auto','uvicorn.protocols.http.auto','uvicorn.protocols.http.h11_impl','uvicorn.protocols.websockets.auto','uvicorn.lifespan.on','sqlalchemy.dialects.sqlite','app.main'],
 hookspath=[],runtime_hooks=[],excludes=['pytest','tkinter','httpx'])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='ResearchHubBackend',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=True,icon=str(root/'desktop/assets/icon.ico'))
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='ResearchHubBackend')
