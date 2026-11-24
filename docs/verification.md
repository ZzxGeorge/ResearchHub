# 验收与测试记录

日期：2026-11-24（Asia/Shanghai）。环境：Windows、Python 3.10.13、Node 24.15.0、npm 11.12.1。测试工作空间与正式资料分离。

## 自动化结果

| 检查 | 结果 |
| --- | --- |
| `.venv/Scripts/python -m pytest --tb=short` | 22 passed；一条上游弃用提示 |
| `npm test`（frontend） | 6 passed，2 个测试文件 |
| `npm run build`（frontend） | TypeScript 与 Vite 生产构建通过；chunk 大小提示 |
| `python -m compileall -q backend scripts` | 通过 |
| start.py / workspace.py `--help` | 通过 |
| 本地 `/api/health`、根页面 | 服务成功启动，页面实际加载 |

## 需求场景映射

| 场景 | 证据与结论 |
| --- | --- |
| 论文 CRUD、PDF、状态 | 参数化 CRUD、附件 API、历史与过滤测试；浏览器创建论文、写笔记、变更状态并看到真实统计变化；实际上传有效测试 PDF，PDF.js 读到 1 页并绘制、缩放 |
| posterior 来自两篇论文 | test_posterior_multiple_papers_merge_preserves_notes_review：归一化匹配、保持一个词汇、两个论文来源、已有手写笔记 / 两条例句 / 复习历史保留 |
| Jacobian / Chain Rule / BPTT | 完整导入测试检查两端关系与方向；浏览器图谱双击 BPTT，详情展示数学前置、使用关系及想法入边 |
| 研究想法 | 示例假设、实验设计、风险、状态被实际保存；详情 / 看板使用真实节点 |
| 完整导入和重导 | 示例经 JSON Schema 与实际 Pydantic 校验，首次创建 7 个节点，重复导入返回原收据；浏览器完成预览并显示新增 7 / 显式关联 5 的报告 |
| 检索 BPTT | API 验证论文、数学、算法、想法、问题五种类别；浏览器搜索返回对应条目；中文 / 混合 / FTS 特殊字符也测试 |
| 词汇复习 | 四种反馈算法参数单测、过期评分 409、调度 / 历史 / CSV；浏览器显示 posterior 答案并选择 Good，本轮计数变为已复习 1 |
| 备份恢复 | 实际 ZIP 快照恢复到独立新工作空间，比较节点、Dashboard、PDF 字节、关联、复习历史与搜索结果；拒绝覆盖存在目录 |
| 典型异常 | 无效 JSON / 版本 / 关系、过期合并、第三次文件写入故障注入、缺失 Markdown、损坏 ZIP、校验失效、ZIP 路径穿越、分类循环、恶意 Host / Origin / 超大请求 |
| 保存可靠性 | Vitest 模拟请求未完成时继续输入，确认串行保存且第二次版本为 2；版本冲突时保留本地草稿并阻止离开 |
| Markdown 安全与公式 | 检查 3 组复杂 KaTeX 公式无 katex-error，表格 / 任务 / Python 高亮；阻止 raw HTML、javascript URL、外部追踪图和不可信 KaTeX 链接 |

## 浏览器验收中修复的问题

- 原生 iframe 在内嵌浏览器中显示空白：替换为 PDF.js 本地 canvas 阅读器，复验真实页面绘制与 125% 缩放。
- React Flow 控制状态没有保存尺寸事件导致节点隐藏：改用 useNodesState，复验图谱节点、边、fit view 与双击跳转。
- 自动化发现布尔参数未声明类型导致回收站 / 非到期复习筛选失败：显式 bool 解析并复验。
- Windows sqlite3 连接上下文并不自动关闭文件句柄：备份恢复改为 contextlib.closing，独立恢复与损坏备份用例通过。
- 完整截图检查发现深色背景和正文颜色未应用到 body：修复继承与按钮对比度，浏览器复验正文 rgb(221,231,225)、背景 rgb(20,27,25)，返回浅色模式。

## 浏览器复验步骤

1. 用独立空目录运行服务，首页全部统计为 0。
2. 创建论文，写含公式和 Mermaid 的 Markdown，保存，回首页确认状态统计。
3. 「导入与导出」粘贴 examples/reading_summary.json，预览 7 条并确认，查看报告。
4. 打开论文预览，核对矩阵、分段函数、期望、求和、积分、代码和流程图。
5. 执行 `python scripts/make_qa_pdf.py`，上传 `.artifacts/browser-qa.pdf`，点击 PDF 分栏，确认页面与缩放。
6. Ctrl+K 搜索 BPTT，核对多个知识库结果；工作台进入复习，显示答案并评分。
7. 图谱选择中心 / 深度，fit view 并双击 BPTT 打开；检查右侧双向关联。
8. 浅色 / 深色及桌面 / 窄屏检查，回到浅色；检查控制台错误。

截图见 `docs/screenshots/`。截图中的数字来自隔离验收工作空间，代表真实测试记录，不作为正式知识库预置数据。

## 尚未证明的事项

没有执行原生 Linux、长时间使用、十万节点压测、真实断电、所有 PDF 字体 / 加密情况、所有浏览器或完整渗透审计。后端 API 验收与本次 UI 操作不代表所有交互已被自动化覆盖。详细边界见 DEVELOPMENT_STATUS.md。
