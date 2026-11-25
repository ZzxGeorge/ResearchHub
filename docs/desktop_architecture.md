# Research Hub Windows 桌面架构 — v0.2.0

React / FastAPI / SQLite / Markdown 业务继续复用。Electron 45.4.1 管理窗口、服务生命周期和有限系统操作；electron-builder 26.18.0 / NSIS 生成当前用户 EXE；PyInstaller 6.22.3 生成后端 onedir，包含 Python 3.10 与迁移 / 前端资源。没有引入远程服务。

## 生命周期

1. Electron 获取单实例锁，读取独立的桌面偏好文件。优先使用 --workspace，再用环境变量、保存的选择、默认 ~/.research-hub/workspace。
2. 生成随机会话令牌与实例 UUID，通过子进程环境传入后端；窗口和渲染器拿不到令牌。使用 windowsHide，不打开终端。
3. 后端获取工作空间 .server.lock，完成安全迁移，再在 127.0.0.1 上绑定端口 0，保留同一个 socket 给 Uvicorn，避免查找空闲端口后的竞争。
4. stdout JSON 通报实际端口与实例；Electron 带令牌检查健康状态和版本，确认它连接的就是本次启动的服务。
5. 受控 session 的 webRequest 仅对本窗口、同源请求注入令牌。后端对包括静态文件、健康检查和导出在内的所有桌面请求鉴权。
6. 页面加载后显示独立窗口。退出先遵循未保存笔记提示，随后关闭本次后端 stdin，等待 Uvicorn 正常停止；超时才终止本次子进程。Electron 异常结束导致 stdin EOF，后端也会停止。

## 安全边界

contextIsolation=true、nodeIntegration=false、sandbox=true、webSecurity=true。preload 暴露 info / chooseWorkspace / openWorkspace / openLogs，以及仅限 rh-theme 和 rh-draft-UUID 的缓存读写接口。缓存键、值长度、主题值和 IPC 来源均校验；不暴露任意文件系统。主进程校验发起者是当前窗口的主 frame 且 origin 一致，IPC 不接受任意命令或文件路径。

外部导航被拦截，仅合法 http(s) 外链经系统浏览器打开；file / javascript / shell 等协议不交给操作系统。PDF 原件和导出使用受控本地下载。禁止 webview；默认拒绝权限，只有当前可信窗口的全屏请求可被允许。CSP 限制资源到本地、禁用 object / frame，KaTeX 与图谱所需内联样式允许；没有关闭 webSecurity。

## 数据与资源

桌面偏好和日志在 Electron userData（通常 %APPDATA%/Research Hub），科研工作空间独立。每个工作空间使用不同的 Chromium storage partition，避免本地草稿、主题等缓存串库。桌面偏好保存路径和窗口信息；额外的私有 UI 缓存按工作空间存放主题和未提交草稿，避免随机端口改变 origin 后丢失恢复入口。缓存不含会话令牌；正式笔记仍写 Markdown / SQLite。

打包资源：resources/backend/ResearchHubBackend.exe + _internal。_internal 下包含 app 模块、migrations 和 frontend/dist。业务代码用 sys._MEIPASS 定位资源，写入始终走外部工作空间。构建的 datas 显式列出 migrations 和 dist，不复制整个仓库。

0002 迁移只增加 reading_positions，引用 attachment_id，JSON 保存 page / scale / offset。升级已有数据库时先使用现有一致性备份服务；备份失败则停止。恢复支持 0001 / 0002，旧快照恢复后可以再次升级。v1 阅读总结协议完全不变。

## PDF 增量

继续使用原 PDF.js 版本、worker / CMap / 字体。组件升级为官方 PDFViewer + PDFLinkService + PDFFindController，惰性绘制可见页，保留 split 入口。文本层提供选择与搜索，高亮由 find controller 管理；缩略图进入视区才绘制，目录来自 PDF 内置 outline。

阅读位置按附件存入 SQLite，在模式切换、离开和 pagehide 时提交；搜索与本地笔记不上传。文档脚本 / 表单批注编辑关闭，eval 不启用。浏览器拒绝系统全屏时使用窗口内阅读覆盖层，并可按 Esc 返回。

参考：[Electron 安全建议](https://www.electronjs.org/docs/latest/tutorial/security)、[NSIS 配置](https://www.electron.build/docs/nsis/)、[PyInstaller 资源打包](https://pyinstaller.org/en/stable/spec-files.html)。
