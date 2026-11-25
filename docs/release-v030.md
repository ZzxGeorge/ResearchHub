# Research Hub v0.3.0 — Interactive Paper Reading

下载 `ResearchHub-Setup-0.3.0-x64.exe`，按向导安装；已有用户可覆盖安装。默认安装到当前用户 Programs 目录，无需 Python 或 Node.js。科研工作空间独立保存，旧数据库升级前自动完整备份。下载后可使用 SHA256SUMS.txt 核验。

- PDF 选文工具栏：快速保存科研英语、数学、算法、个人想法和问题；原文插入论文笔记，保留最新编辑草稿。
- 统一 SourceAnchor，保存实际文件页序、多行/跨页 PDF 坐标、原始和清理文本、上下文及附件 SHA256。原文与知识双向跳转，文件缺失/变化时阻止错误定位。
- 词汇候选确认与跨论文追加，保留原笔记、优先级、掌握和 SM-2 历史；未补释义的词汇可集中完善。
- 柔和多色/自定义高亮、Markdown/LaTeX 批注和独立批注修订；原始 PDF 不被修改，解除关联或删除高亮不会删除全局知识。
- 本篇知识收集面板、搜索/排序/关联，阅读模式/分栏/标签/位置/旋转及快速录入草稿恢复。
- 六种可编辑 ChatGPT 提问模板，一键复制；明确个人笔记、AI 辅助解释和论文原文来源。保留 reading-summary v1 与重复项预览合并流程。

54 项自动化检查通过（后端 36、前端 15、桌面策略 3）；另完成 TypeScript/Vite、PyInstaller/NSIS、清理开发 PATH 的打包后端、本机覆盖安装、实际桌面启动和真实 v0.2 工作空间升级保留校验。阅读交互使用独立公共 PDF 在内嵌浏览器验证；原生窗口自动化存在截图/坐标不一致，完整 Electron PDF 交互尚未全部验证。

未验证干净 Windows 10/11 或所有复杂/加密/超大 PDF。区域截图、图表摘录、OCR 属后续 P3，未实现。安装包未数字签名；请使用安装包及标准目录，不直接运行 Codex 工作区中的 win-unpacked。

详见 README、docs/interactive_reading.md、docs/source_anchor_model.md 和 docs/verification-v030.md。发布附件仅包含程序，不包含任何个人论文、笔记、数据库或凭证。
