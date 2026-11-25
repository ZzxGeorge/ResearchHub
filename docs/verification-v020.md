# v0.2.0 实际验收记录

日期 2026-11-25，Windows 11 x64，Python 3.10.13 / Node 24.15.0。安装包是实际 NSIS EXE，非浏览器快捷方式。打包链为 Electron 45.4.1、electron-builder 26.18.0、PyInstaller 6.22.3。

| 检查 | 实际结果 |
| --- | --- |
| Git 基线 | 新建本地 Git，提交 2817324，tag v0.1.0；不含科研工作空间 |
| 后端 | 25 passed，含原有 22 项 |
| 前端 | 7 passed，3 个文件 |
| 桌面策略 | 3 passed：同源 / 外链协议 / 窗口位置 |
| 前端 / 后端 / EXE 构建 | TypeScript、Vite、PyInstaller onedir、Electron、NSIS 均成功 |
| v1 协议 | git diff 确认 Schema 与配套提示词无变更 |
| 实际旧库迁移 | 用 v0.1.0 tag 的代码在中文目录创建论文 / PDF / 词汇 / 复习与关系，当前版本迁移后逐项比较相等，完整备份可恢复 |
| 包装后端 | 清理开发 PATH、中文运行 / 数据目录；健康身份、未授权读 401、静态 / PDF 本地资源、导入 / 检索、重复服务拒绝、退出码 0 |
| 安装 | NSIS /S 当前用户安装，退出 0，桌面与开始菜单快捷方式存在，卸载程序存在 |
| 覆盖安装 / 卸载重装 | 同版覆盖、卸载、重新安装均执行，隔离 QA 文件指纹保持一致；最后重新安装保留可用程序 |
| 桌面启动 | 从标准 Programs 目录运行，真实 Research Hub 窗口显示本地工作台，后端日志确认启动与正常关闭 |
| PDF 生产前端 | 中文文件名；3 页；双栏、向量 / 位图、图像页；文本层选择出 copy；posterior 命中 2 项并显示高亮；缩略图 / outline；第 2 页与整页缩放恢复；仅 PDF / 仅笔记 / 原分栏；全屏回退；坏 PDF 显示 InvalidPDFException 后仍可返回工作台 |

## 报告与复现

- `.artifacts/build-windows-v020.log`：完整构建日志。
- `.artifacts/desktop-backend-smoke.json`：包装后端实际检查。
- `.artifacts/installer-verification.json`：安装 / 卸载 / 覆盖与 SHA256。
- `release/BUILD_INFO.json`：最终发行文件大小、SHA256、版本、测试摘要。
- `scripts/smoke_backend.py`：在独立数据目录验证打包可执行文件。
- `scripts/verify_installation.py`：显式安装生命周期验收脚本，会操作本机当前用户安装的 Research Hub；不应在正在使用正式桌面应用时运行。
- `scripts/make_reader_fixture.py`：生成公开的三页 PDF 测试夹具，不读取真实论文。
- `docs/screenshots/pdf-v020-search.jpg`、`pdf-v020-fullscreen.jpg`：隔离预览实际截图。

## 启动异常的实因

初次直接运行源码目录内 win-unpacked 时，Electron 日志明确报告 AppContainer package SID 存在而 ALL APPLICATION PACKAGES 读取 ACE 不存在，沙盒无法读取该程序目录，因此触发 fatal / 0x80000003。该进程没有打开正式知识库。未按日志建议修改 ACL，也未用 --no-sandbox。通过 NSIS 安装到普通 `%LOCALAPPDATA%/Programs/Research Hub` 后，应用正常启动。

## 验证边界

原生桌面自动化的截图 / 几何返回不可靠，已避免继续向可能错误的窗口输入。桌面成功启动由原生窗口可访问性树及应用 / 后端日志确认；PDF 完整交互在隔离内嵌浏览器的同一生产前端进行。此记录不将浏览器 PDF 验收等同于所有 Electron 集成已经验收。

未拥有干净 Windows 10/11 虚拟机；未实际验证所有快捷键、多 DPI / 显示器、全部复杂论文、目录切换重启、下载 / 全屏权限集成、异常杀进程每个时点。没有签名和 SmartScreen 放行测试。不存在“所有 Windows 环境已认证”或“绝无数据丢失”的结论。后续工作见 DEVELOPMENT_STATUS.md。
