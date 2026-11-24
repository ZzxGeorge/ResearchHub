# 数据库设计

数据库：`database/hub.sqlite3`，SQLite WAL + `synchronous=FULL` + 外键校验。版本由 Alembic 表 `alembic_version` 管理，初始版本 `0001`。UTC 时间使用带时区 ISO 8601 字符串，前端按浏览器时区展示。

| 表 | 主键 | 职责 / 关键字段 |
| --- | --- | --- |
| nodes | id (UUID) | kind、title、normalized_title、status、tags_json、metadata_json、note_path、version、created_at、updated_at、deleted |
| revisions | id (UUID) | node_id 外键、version、note_path、snapshot、created_at；(node_id, version) 唯一 |
| relations | id (UUID) | source / target 节点外键、type、description、evidence、created_at；(source,target,type) 唯一 |
| attachments | id (UUID) | node_id 外键、原始安全文件名、相对路径、MIME、SHA256、字节数、时间 |
| review_states | node_id 外键 | repetitions、interval_days、ease、due_at、last_review、lapses、version |
| review_logs | id (UUID) | node_id 外键、rating、reviewed_at、完整 before_json / after_json、algorithm |
| import_receipts | digest (SHA256) | report_json、created_at；相同规范化导入包幂等 |
| categories | id (UUID) | kind、name、parent_id 自关联；服务层检查循环与类别一致性 |
| search_index | FTS5 虚拟表 | node_id、归一化 text；正文与元数据的可重建索引 |

## 节点模型

kind 为 paper / vocabulary / mathematics / algorithm / idea / question。tags_json 为可编辑标签数组，metadata_json 为经 Pydantic Metadata 严格校验的结构；字段字典见生成的 JSON Schema。多个类别知识可共用相同字段，但正文仅保留在所属节点的 Markdown 文件中。

选用统一节点而非六套正文表，是为了避免跨模块关联出现多态外键失效。论文作者、机构、方向等列表按 JSON 存储，优先保证单用户应用的迁移与导出简单。未来需要高级统计时可通过新增迁移拆分结构，保留节点 UUID。

阅读状态和复现状态分开：nodes.status 表示阅读进度；metadata.reproduction_status 表示 none/planned/in_progress/completed。重要性、优先级和掌握程度是独立字段。

## 正文与修改历史

nodes.note_path 指向模块目录下 `UUID/v版本-随机UUID.md`。每次成功修改都会创建新文件和 revisions 记录，snapshot 包含该版本标题、状态、标签和元数据。读取当前笔记直接读取当前文件；读取历史使用历史文件。snapshot 不包含第二份正文。

写入需要 expected_version，过期提交返回 409。软删除保留所有文件与关系，回收站可恢复；删除 / 恢复会增加乐观版本，但不新增正文版本。附件与关联变化不改变正文版本。手动合并会为目标创建正文版本，将源节点移入回收站，并复制有效关联。

## 关系语义

uses、depends_on、derived_from、extends、prerequisite_of、inspired_by、validates、contradicts 为有向边。例如 A prerequisite_of B 表示 A 是 B 的前置知识。

related_to 与 compares_with 为对称边，source/target 按 UUID 排序后存储，避免 A→B 与 B→A 重复。所有详情同时查询两端，显示方向、说明与证据。删除节点后默认图谱和详情隐藏与其有关的边；恢复后重新出现。

## 词汇身份与来源

normalized_title 用 NFKC + casefold + 空白折叠生成。title 不设置全局唯一约束，因为同形词、词性和词义可以不同。候选匹配综合 normalized_title、part_of_speech 和 sense，始终经导入预览确认；不通过自动删除历史来去重。

来源论文用关系存储，章节 / 页码 / 多语境例句保存在 metadata 列表中。合并导入已有词汇不会重置 review_states 或 review_logs。当前不支持将两个已有词汇复习队列手动合并，以免丢失调度语义。

## 搜索

FTS5 unicode61 进行英文词项搜索，参数化 LIKE 使用转义后的归一化字面子串作为中文 / 混合回退。写入和软删除在同一事务更新索引，文件外部修改后需手动重建。类别、标签与日期过滤以真实结构化元数据为准。

## 演进与恢复

迁移脚本冻结 SQL，避免运行时模型变化篡改旧版本迁移。当前仅有初始迁移；后续版本必须新增迁移、先在备份副本上测试。备份使用 SQLite backup API，不直接复制活动 WAL 数据库文件。备份包含所有受管理、被引用的正文历史和附件。
