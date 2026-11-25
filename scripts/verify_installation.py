"""Explicit installer acceptance; only the isolated QA workspace is fingerprinted."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
def fingerprint(directory):
    return {str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.rglob('*') if p.is_file() and not p.name.endswith(('.lock','-shm','-wal'))}
def main():
    install=Path(os.environ['LOCALAPPDATA'])/'Programs/Research Hub'
    installer=ROOT/'release/ResearchHub-Setup-0.2.0-x64.exe'
    qa=ROOT/'.test-workspaces/electron-qa'
    assert qa.is_dir() and (install/'Uninstall Research Hub.exe').is_file()
    before=fingerprint(qa)
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    # Generated uninstaller removes application resources, never the QA or user knowledge workspace.
    subprocess.run([str(install/'Uninstall Research Hub.exe'),'/S'],check=True,creationflags=flags)
    for _ in range(180):
        if not (install/'Research Hub.exe').exists():break
        time.sleep(.25)
    assert not (install/'Research Hub.exe').exists(),'Uninstallation did not complete'
    assert fingerprint(qa)==before,'QA data changed on uninstall'
    subprocess.run([str(installer),'/S','/D='+str(install)],check=True,creationflags=flags)
    assert (install/'Research Hub.exe').is_file()
    assert fingerprint(qa)==before,'QA data changed on reinstall'
    subprocess.run([str(installer),'/S','/D='+str(install)],check=True,creationflags=flags)
    assert fingerprint(qa)==before,'QA data changed on overwrite install'
    report={'version':'0.2.0','install_directory':str(install),'installer':str(installer),'installer_sha256':hashlib.sha256(installer.read_bytes()).hexdigest(),'uninstall_reinstall_overwrite':True,'qa_files_preserved':len(before),'desktop_shortcut':(Path.home()/'Desktop/Research Hub.lnk').is_file(),'start_menu_shortcut':(Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Research Hub.lnk').is_file(),'clean_windows_test':False}
    destination=ROOT/'.artifacts/installer-verification.json';destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(destination)
if __name__=='__main__':main()
