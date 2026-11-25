# Windows 安装、升级、数据与重新构建

## 安装和启动

双击 release/ResearchHub-Setup-0.2.0-x64.exe。默认当前用户安装到 `%LOCALAPPDATA%/Programs/Research Hub`，向导支持更改目录；提供桌面与开始菜单快捷方式、系统卸载入口。安装后双击 Research Hub，程序自动启动本地服务，不需要 Python / Node / PowerShell / 浏览器。

本次安装包未签名，可能出现未知发布者 / SmartScreen 提示。由用户自行核验文件来源及 SHA256 后处理系统提示；不建议关闭系统安全功能。发行前可以接入自己的 Authenticode 证书重新签名。

请运行安装后的快捷方式，不要从源码目录的 release/win-unpacked 运行。该工作区含有 Codex 的 AppContainer 专用权限，Electron 45 在此可能报 0x80000003；标准当前用户 Programs 安装位置已成功启动。没有更改系统 ACL 或关闭 Electron 沙盒。其他受限自定义目录也需要另行验证。

## 使用原有资料

默认直接使用 `~/.research-hub/workspace`。若此前用其他目录，关闭浏览器版服务后，在桌面版「设置 → 切换工作空间」选择原目录并重启；也可首次运行时加 `--workspace "D:\ResearchWorkspace"`。不要选择软件安装目录。设置可查看当前路径并打开工作空间或日志目录。

所有数据库、Markdown、PDF、附件、复习历史和关联留在外部工作空间。安装 / 覆盖安装 / 卸载只操作程序资源，默认不删除知识库。升级之前建议另外保存一份完整备份。数据库从 0001 升为 0002 前会自动在 backups 生成一致性 ZIP；迁移失败则停止启动并在错误 / 日志中提供备份位置，不用空库替换旧库。

恢复方法：用原项目 CLI `scripts/workspace.py restore 备份.zip --target 一个不存在的新目录`，然后选择该目录启动。升级后不要直接用旧版代码打开更高版本数据库；如需回到 v0.1.0，请恢复迁移前备份到另一个新目录。

## 关闭与故障

关闭窗口前完成笔记保存。未保存时应用会提示，允许留在应用中继续处理；草稿另存于所选工作空间对应的桌面浏览器 profile。窗口退出后后端正常停止；异常退出时 stdin EOF 也会停止服务。

启动失败请查看「打开应用日志」或 Electron userData 下 logs/desktop.log、logs/backend.log。若工作空间已被另一个桌面服务锁定，先退出那个实例；不要删除数据库来“修复”启动错误。Web 开发模式继续使用 scripts/start.py，正式使用时不要同时用多个服务打开同一个知识库。

## 重新构建

开发机安装 Windows x64、Python 3.10+、Node 22/24 和 npm，在源码根目录运行：

```powershell
.\scripts\build_windows.ps1
```

脚本检查环境、安装锁定运行与构建依赖、npm ci、构建前端、生成图标、PyInstaller onedir、Electron 打包及 NSIS 安装包，打印路径与 SHA256。已有依赖可运行 `-SkipInstall`。前端 / 后端 / 壳的版本号更改时需同步安装包名称。构建时需要联网下载依赖和官方打包工具；安装后核心功能离线运行。

产物在 release，临时构建在 build。不要把正式数据放进这些目录。目录外的数据不被构建脚本扫描。源码中 .gitignore 排除了数据、PDF、ZIP、release、build 和 node_modules。

## 验证范围

当前实测为此 Windows 11 开发机。清洁 Windows、Windows 10、SmartScreen 实际放行流程、全部显示器 / DPI 组合仍需独立验证。详细结果见 verification-v020.md。
