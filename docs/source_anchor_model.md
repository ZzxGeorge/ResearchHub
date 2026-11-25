# Source Anchor 与批注实现

v0.3.0 使用 Alembic `0003`（父版本 `0002`），保留既有统一 Node、语义 Relation、附件、修订和复习表。新增表不改变 reading-summary v1。

| 实体 | 字段与用途 |
| --- | --- |
| source_anchors | UUID；paper_id 与 attachment_id 外键；pdf_sha256；从 1 开始的文件页码 page；可选 printed_page；raw_text / cleaned_text / context / section / notes；rects_json；version / deleted / timestamps |
| source_links | (anchor_id, node_id) 联合主键，表示出处，不代替语义 Relation；一个出处对应多个知识，反向亦然 |
| annotations | 一个 anchor 对应一个可编辑的颜色、颜色含义和批注；note_path 指向当前不可变 Markdown；乐观版本、软删除和时间戳 |
| annotation_revisions | 批注每次保存的新文件指针、版本及颜色/标签快照，旧文件不覆盖 |
| paper_reading_states | 每篇论文的模式、分栏比例、面板、所选来源/知识、附件、快速录入草稿 JSON；与每附件 reading_positions 分开，避免位置更新覆盖草稿 |

矩形示例：`[{"page":4,"rect":[72,580,180,594]},{"page":5,"rect":[72,700,240,714]}]`。每个 rect 是 `[x_min,y_min,x_max,y_max]`，单位为 PDF 页面 user-space 点，遵循 PDF.js 页视口；page 为实际文件页序，不是印刷页码。多行、多列和跨页保留多个非空矩形，保存原始文本及独立清理结果。禁止非有限、反向、空或过多矩形。

前端使用原生 Selection / Range，从 PDF.js Text Layer 获取选文与行矩形，按每页实际 CSS 边界映射到 `viewport.convertToPdfPoint`；持久化从不依赖屏幕像素、DPI 或当前 DOM。显示时使用 `convertToViewportRectangle`，兼容缩放、旋转和分栏尺寸。只为已渲染 canvas 的页面创建覆盖层，PDF.js 继续负责连续阅读和页面回收。覆盖层 `pointer-events:none`，页边来源标记可点击。页面文本缓存最多 8 页；上下文仅在可确认原文匹配时截取，不自动猜测章节。

附件文件名为不可变 UUID 路径，SHA256 存于附件及来源。打开阅读器、创建定位和解析来源时核验实际文件；哈希/所属论文不符、缺失或回收站论文会阻止坐标应用。界面选择另一附件不会复用旧附件的覆盖层。页码超出当前 PDF 在阅读器中拒绝。外部绕过应用在文件校验后立即写入同一路径的竞争，不属于正常附件工作流；请勿直接修改工作空间文件。

写入遵循工作空间 FileLock 和 SQLAlchemy 事务。快速保存将 Node / 修订 / SourceAnchor / SourceLink / 自动论文语义关系一次提交；已有条目先检查版本。追加复用 merge_data，保留旧标量、追加正文与列表，冲突另存供核对；不重建 ReviewState / ReviewLog。批注先原子写入新 Markdown 文件，再提交 SQLite 指针和修订，失败时最多留下未引用文件，不覆盖原数据，不自动垃圾回收。

`GET /api/sources/{id}` 是带文件核验的定位解析；`POST /api/reading/capture` 是统一快速创建；来源链接、批注、论文收集和 reading-workspace 使用各自端点。删除定位/批注为软删除，解除链接不删除 Node；回收论文不删除原文文件。当前没有物理删除 PDF 接口。

完整 JSON 导出新增 reading_data_version、source_anchors、source_links、annotations、annotation_revisions、paper_reading_states，包含批注正文和修订正文；ZIP 备份包含引用的所有文件。恢复检查校验和、外键、迁移版本及文件引用。JSON 导出是快照，不是 v1 总结导入格式；整库迁移使用 ZIP。

论文笔记插入先保存/关联来源，再操作最新客户端正文，由现有 Node 乐观版本自动保存处理，不能用一次服务器旧正文覆盖用户未保存的编辑。阅读草稿用独立序列化写队列和本机缓存；离开页面前等待保存结果。多窗口同时修改论文笔记会触发版本冲突；阅读 UI 状态为单窗口使用的最后写入值，不支持多人协作。
