"""Publish the verified Windows installer; Git credentials remain in process memory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse
import httpx

ROOT = Path(__file__).resolve().parents[1]
REPO = 'ZzxGeorge/ResearchHub'
API = 'https://api.github.com/repos/' + REPO

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()

def credential():
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        return token
    result = subprocess.run(['git', 'credential', 'fill'], cwd=ROOT,
                            input='protocol=https\nhost=github.com\npath='+REPO+'.git\n\n',
                            capture_output=True, text=True, timeout=120)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if result.returncode or not values.get('password'):
        raise RuntimeError('GitHub authentication is required. Sign in through Git Credential Manager, then retry.')
    return values['password']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default='v0.2.0')
    args = parser.parse_args()
    info = json.loads((ROOT/'release/BUILD_INFO.json').read_text(encoding='utf-8'))
    if args.tag != 'v'+info['version']:
        raise RuntimeError('Tag and built artifact version do not match')
    exe = ROOT/'release'/f'ResearchHub-Setup-{info["version"]}-x64.exe'
    checksum = ROOT/'release/SHA256SUMS.txt'
    expected = digest(exe)
    if expected != info['sha256'] or checksum.read_text(encoding='utf-8').strip() != expected+'  '+exe.name:
        raise RuntimeError('Installer checksum verification failed; refusing to publish')
    target = subprocess.check_output(['git','rev-parse',args.tag], cwd=ROOT, text=True).strip()
    if target != info['commit']:
        raise RuntimeError('The version tag does not match the verified build commit')
    body = f'''Research Hub {args.tag} — Windows 桌面应用与 PDF 阅读增强

## 安装
下载 `{exe.name}`，按向导安装，再从桌面或开始菜单启动。安装后不需要 Python、Node.js 或外部浏览器。可用 SHA256SUMS.txt 核验下载文件。

## 功能
- 本地科研知识库：论文、词汇、数学、算法、科研想法、问题。
- Electron 桌面窗口与自动后端管理；设置中选择独立工作空间。
- PDF 连续阅读、文本选择、搜索高亮、目录、缩略图、分栏与阅读位置恢复。
- Markdown / LaTeX / Mermaid、知识关联、导入、搜索、词汇复习与完整备份。

## 数据与验证边界
默认沿用 `~/.research-hub/workspace`，数据库迁移前自动备份；安装和卸载默认保留科研资料。此附件不包含任何个人知识库。

后端 25、前端 7、桌面策略 3 项自动化测试通过；本机 Windows 11 标准安装、卸载重装、覆盖安装已验证。未在干净 Windows 10/11 环境全面验证，全部 Electron PDF 集成交互仍需补充验收。进阶批注、摘录联动和 OCR 尚未实现。

安装包未进行数字签名，可能显示 SmartScreen 或未知发布者提示。请使用标准安装目录；不要直接运行 Codex 源码目录中的 win-unpacked 包。

详见仓库 README.md、DEVELOPMENT_STATUS.md 和 docs/verification-v020.md。
'''
    with httpx.Client(headers={'Authorization':'Bearer '+credential(),
                               'Accept':'application/vnd.github+json',
                               'X-GitHub-Api-Version':'2022-11-28'}, timeout=120) as client:
        def call(method, url, **kwargs):
            response = client.request(method, url, **kwargs)
            if response.is_error:
                raise RuntimeError(f'GitHub API returned {response.status_code} for {urlparse(url).path}; no credential details are logged')
            return response.json()
        response = client.get(API+'/releases/tags/'+args.tag)
        if response.status_code == 404:
            # A draft is published only after every attachment has been checked.
            release = call('POST', API+'/releases', json={'tag_name':args.tag,'target_commitish':target,
                           'name':'Research Hub '+args.tag,'body':body,'draft':True,'prerelease':False})
        elif response.is_success:
            release = response.json()
        else:
            raise RuntimeError(f'Cannot inspect release: HTTP {response.status_code}')
        upload = release['upload_url'].split('{',1)[0]
        parsed = urlparse(upload)
        if parsed.scheme != 'https' or parsed.netloc != 'uploads.github.com':
            raise RuntimeError('Unexpected GitHub asset upload host')
        existing = {a['name']:a for a in call('GET', API+f'/releases/{release["id"]}/assets')}
        assets = []
        for path in [exe, checksum]:
            local_digest = digest(path)
            if path.name in existing:
                asset = existing[path.name]
                if asset.get('digest') != 'sha256:'+local_digest:
                    raise RuntimeError('A different or unverified asset already exists; no files were replaced')
            else:
                print('Uploading '+path.name+' ('+str(path.stat().st_size)+' bytes)', flush=True)
                with path.open('rb') as stream:
                    asset = call('POST', upload, params={'name':path.name},
                                 content=iter(lambda:stream.read(1024*1024),b''),
                                 headers={'Content-Type':'application/octet-stream','Content-Length':str(path.stat().st_size)})
            if asset['state']!='uploaded' or asset['size']!=path.stat().st_size:
                raise RuntimeError('Uploaded asset is incomplete; draft remains unpublished')
            if asset.get('digest') and asset['digest'] != 'sha256:'+local_digest:
                raise RuntimeError('GitHub asset digest does not match the local artifact')
            assets.append({'name':asset['name'],'url':asset['browser_download_url'],'bytes':asset['size'],'sha256':local_digest})
        if release['draft']:
            release = call('PATCH', API+f'/releases/{release["id"]}', json={'draft':False})
        result = {'repository':REPO,'release_url':release['html_url'],'tag':args.tag,'assets':assets}
        output = ROOT/'.artifacts/github-release-report.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2), encoding='utf-8')
        print(release['html_url'])

if __name__=='__main__':
    main()
