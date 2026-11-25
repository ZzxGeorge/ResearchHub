# Research Hub v1.0 导入格式

权威协议是 [reading-summary-v1.schema.json](../schemas/reading-summary-v1.schema.json)，由 `backend/app/schemas.py` 的 Pydantic 模型生成；API `/api/import/schema` 使用同一模型。不要在 Schema、提示词和代码间手动维护三份不一致定义。

## 顶层字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| schema_version | "1.0" | 必填；其他版本拒绝导入 |
| paper | Entry | 必填，唯一论文，kind=paper |
| literature_note | string | 完整 Markdown 精读笔记，默认空 |
| vocabulary | Entry[] | kind=vocabulary，默认空 |
| mathematics | Entry[] | kind=mathematics，默认空 |
| algorithms | Entry[] | kind=algorithm，默认空 |
| research_ideas | Entry[] | kind=idea，默认空 |
| questions | Entry[] | kind=question，默认空 |
| relations | Relation[] | 仅引用本包条目 key，默认空 |
| reading_summary | string | 附加到论文的阅读总结，默认空 |

## Entry 字段

必填 `key`、`kind`、`title`。key 以英文字母开头，仅含英文数字 / 下划线 / 短横线，最长 80 字符，整个包不可重复。title 必须非空，最长 1000 字符。其余字段可省略：

- markdown：Markdown 正文，最长 2,000,000 字符。
- metadata：结构化字段对象，见下表及完整 Schema。
- tags：字符串数组，最多 100 个标签。
- status：类别对应状态；省略使用类别默认状态。
- match_id：已知本地 UUID，可为 null；未知时省略。它只是候选匹配信息，不构成覆盖许可。

JSON 中 Markdown 换行用 `\n`，LaTeX 的每个反斜线用 `\\`。不要将 Python None、注释或尾逗号写入 JSON。可选字段未知时优先省略；只有 Schema 中允许 null 的字段才接受 null，不把所有字段统一设置为 null。

## metadata 字段分组

| 分组 | 字段 |
| --- | --- |
| 论文名称 | chinese_title、english_name、abbreviation |
| 发表信息 | authors[]、institutions[]、year (1800–2200 或 null)、venue、doi、arxiv_id |
| 链接 | url、project_url、code_url |
| 内容与分类 | abstract、directions[]、keywords[]、category_ids[] |
| 阅读 | reading_start / reading_end (YYYY-MM-DD 或 null)、importance (1–5)、priority (1–5)、reproduction_status、worth_reproducing、reread |
| 词汇 | part_of_speech、sense、vocabulary_category、meaning、contextual_meaning、collocations[]、examples[]、translations[]、sources[]、mastery (0–5) |
| 数学 | textbooks[]、textbook_chapters，正文中记录定义 / 推导 / 应用 |
| 想法 | idea_date (日期或 null)、experiment_path、next_action，正文记录假设 / 路线 / 设计 / 失败原因 |
| 问题 | question_type、resolved_at (字符串或 null)、next_action，正文记录解决过程与结论 |

除注明的数字、布尔、列表、日期 / null 外，其余都是字符串。所有字段的默认值和精确类型见 JSON Schema。category_ids 是本机已有分类 UUID，ChatGPT 不知道时必须省略；它可以填写 directions 自由文本领域名称。正文丰富字段不另存一份 metadata 字符串。

vocabulary_category：general_academic / mathematical / technical / phrases / writing。
question_type：english / mathematics / algorithm / code / experiment / research。

状态与优先级规则见 [提示词](chatgpt_export_prompt.md)。5 是最高优先级，0 是尚未掌握，5 是完全掌握。

## Relation 字段

source、target 为本导入包 key；type 是规定的十种关系之一；description 和 evidence 是可选说明 / 页码证据。禁止自关联和悬空引用。外部已有条目可在本包声明一个 Entry，预览中选择合并或跳过并映射到该条目，再引用其 key。

每个成功导入的非论文条目自动建立 derived_from 指向本包论文，因此词汇第二次来自另一篇论文时能保留多个来源。显式重复边会合并说明与证据。

## 预览与提交

1. `/api/import/preview` 接收整个 ImportBundle，校验集合类型、key、状态和关系引用，返回每个条目的候选项、版本、元数据与正文。
2. UI 为精确 DOI / arXiv、显式 UUID、相同词汇+词性+词义提供合并建议。相同标题或词义不确定项默认新增，用户可自行调整。
3. `/api/import/commit` 接收 `{bundle, decisions}`。decisions 的键必须等于全部 Entry key；每个值包含 action=new/merge/skip。merge 必须含 target_id 和 expected_version；skip 可以携带目标映射以保留关系。
4. 提交前校验所有目标版本。在一个事务中保存所有节点、关系、搜索索引和导入收据。Markdown 先安全写入新版本，失败则数据库回滚，旧版本仍可读。
5. 相同规范化导入 JSON 的 SHA256 已存在时返回原报告。幂等按内容判断；修改内容后重新预览并明确选择合并，避免无意新增。

合并策略：旧标题 / 状态 / 非空标量默认保留，列表去重追加，新的正文附加为「导入补充」。有冲突的结构化字段会以 JSON 差异附到笔记，供用户人工修改。此版本不提供逐字段覆盖开关；用户可在导入完成后在基本信息中明确编辑。

## 示例演示

用独立新数据目录启动应用，粘贴或选择 `examples/reading_summary.json`。预览 7 个条目，首次全部新增。确认后创建 1 论文、1 词汇、2 数学、1 算法、1 想法、1 问题，并建立来源和显式关系。搜索 BPTT 会命中多个知识库。再次导入相同文件，返回原报告且数量不变。

验证 posterior 多来源：复制示例，修改 paper.title 和词汇 sources / examples；其他知识选跳过，论文选新增，posterior 选择合并并检查词义；确认后该词汇能看到两篇来源论文，复习历史保留。

## 异常处理

| 情况 | 行为 / 用户处理 |
| --- | --- |
| 无效 JSON / 多余字段 / 错误版本 / 非法状态 | 422，不写入；根据字段路径修正 |
| key 重复 / 悬空关联 | 422，不写入；检查 key 引用 |
| 文件 >10 MB | 前端或请求体限制拒绝；拆分为单篇总结 |
| 合并目标已修改 | 409，重新预览比较并确认；不覆盖新内容 |
| 同形词词义不同 | 显示候选原因，默认新增；由用户判断 |
| 磁盘或权限故障 | 整个结构化事务回滚；旧笔记不变；可留下未引用新文件，暂不自动清理 |
| Markdown / 附件缺失 | 明确报错；从完整备份恢复至新工作空间 |
| JSON 中含外部文件路径 | 不会自动读取或上传。附件需通过详情页另行上传 |
| 完整库 JSON 导出 | 与单篇 ImportBundle 协议不同；完整恢复使用备份 ZIP |

未来协议升级必须保留旧 Schema 或提供明确迁移器；不能静默将未知版本当作当前版本。


## v0.3 阅读中收集与总结导入

原 v1 Schema 保持字节级兼容。使用 [交互阅读后导入示例](../examples/interactive_reading_v1.json) 练习：先手动收集同名词汇，再预览并明确选择合并。精确 SourceAnchor 与复习历史由本机保留；不要让 ChatGPT 生成坐标、附件 UUID 或哈希。导入正文用标题区分 AI 辅助解释与个人笔记。整库数据含新阅读实体的迁移使用 ZIP 备份，不把快照 JSON 当成阅读总结 v1。
