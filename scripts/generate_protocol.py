"""Regenerate the checked-in JSON Schema and exact matching ChatGPT prompt."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.schemas import ImportBundle

schema=ImportBundle.model_json_schema()
schema['$schema']='https://json-schema.org/draft/2020-12/schema'
schema['$id']='urn:research-hub:reading-summary:1.0'
value=json.dumps(schema,ensure_ascii=False,indent=2)+'\n'
(ROOT/'schemas').mkdir(exist_ok=True)
(ROOT/'schemas/reading-summary-v1.schema.json').write_text(value,encoding='utf-8')
prompt='''# ChatGPT 论文阅读总结导出提示词

复制以下内容发送至该篇论文的 ChatGPT 阅读对话。生成结果保存为 UTF-8 JSON，进入 Research Hub「导入与导出」校验并预览。

---

请根据本对话实际讨论、论文原文以及我明确表达的个人理解，导出一份 Research Hub v1.0 结构化阅读总结。只输出一个合法 JSON 对象，不要用 Markdown 代码围栏包裹，不要输出对象以外的说明。

严格遵循下面完整 JSON Schema。schema_version 必须是 "1.0"。paper.kind 为 paper；vocabulary 中 kind 为 vocabulary；mathematics 中为 mathematics；algorithms 中为 algorithm；research_ideas 中为 idea；questions 中为 question。所有条目的 key 全局唯一，以字母开头，仅含英文数字、下划线、短横线。relations.source 和 target 只能引用这份文件中的 key，不得引用标题。不要猜测本地 UUID；match_id 未知时省略。

仅填写已知字段；未知的可选字段省略，只有 Schema 允许 null 的字段可填 null。不要编造 DOI、引用、实验数值、出处、创新性或我的观点。没有提及的知识集合用空数组或省略。来源页码或章节写入 metadata.sources（字符串数组），并在关系 evidence 中注明来源。默认导入会为知识与论文建立 derived_from 关系，可额外声明算法 uses 数学、想法 inspired_by 论文等。

paper.markdown 用于短摘要也可为空；完整精读笔记放 literature_note，避免重复。正文是 Markdown 字符串，支持 $行内公式$、$$独立公式$$、表格、Python 代码围栏、Mermaid 围栏。JSON 中换行写成 \\n、LaTeX 反斜线写成 \\\\；确保可由 JSON.parse 解析。论文笔记请覆盖研究问题、核心创新、架构、数学推导、训练推理、实验、局限、复现、个人理解、启发和未解决问题；不要为填满模板而编造内容。

词汇的 title 为英文单词或短语；metadata.part_of_speech、sense 明确区分不同词性和词义，同一词义仅创建一次，将不同语境累积在 contextual_meaning、examples、translations、sources。数学知识按主题复用；算法描述与数学推导通过关系连接。科研想法保留假设、实验设计、风险和被否定原因，不把假设写成已验证结论。

状态枚举：paper=to_read/skimmed/reading/completed/archived；复现另用 metadata.reproduction_status=none/planned/in_progress/completed。idea=inspiration/survey/definition/design/experiment/analysis/writing/completed/paused/rejected；question=open/in_progress/resolved/paused；其余=learning/mastered。priority 和 importance 是 1–5，5 为最高；mastery 为 0–5。

v0.3 阅读中手动收集的知识可能已存在。请保持准确的 title、词性和 sense，方便导入预览匹配；仅在我提供可靠本地 UUID 时使用 match_id。导入时由我选择追加合并，不应让新总结覆盖个人笔记或复习历史。将 AI 辅助解释、论文作者结论和个人研究假设分开标记。v1 不包含精确 PDF 坐标，不要编造附件 ID、文件哈希或选区；已有原文定位由软件保留。

完整 JSON Schema（这是软件模型生成的实际协议）：

```json
'''+value+'''```
'''
(ROOT/'docs/chatgpt_export_prompt.md').write_text(prompt,encoding='utf-8')
print('Generated schema and matching export prompt')
