# ChatGPT 论文阅读总结导出提示词

复制以下内容发送至该篇论文的 ChatGPT 阅读对话。生成结果保存为 UTF-8 JSON，进入 Research Hub「导入与导出」校验并预览。

---

请根据本对话实际讨论、论文原文以及我明确表达的个人理解，导出一份 Research Hub v1.0 结构化阅读总结。只输出一个合法 JSON 对象，不要用 Markdown 代码围栏包裹，不要输出对象以外的说明。

严格遵循下面完整 JSON Schema。schema_version 必须是 "1.0"。paper.kind 为 paper；vocabulary 中 kind 为 vocabulary；mathematics 中为 mathematics；algorithms 中为 algorithm；research_ideas 中为 idea；questions 中为 question。所有条目的 key 全局唯一，以字母开头，仅含英文数字、下划线、短横线。relations.source 和 target 只能引用这份文件中的 key，不得引用标题。不要猜测本地 UUID；match_id 未知时省略。

仅填写已知字段；未知的可选字段省略，只有 Schema 允许 null 的字段可填 null。不要编造 DOI、引用、实验数值、出处、创新性或我的观点。没有提及的知识集合用空数组或省略。来源页码或章节写入 metadata.sources（字符串数组），并在关系 evidence 中注明来源。默认导入会为知识与论文建立 derived_from 关系，可额外声明算法 uses 数学、想法 inspired_by 论文等。

paper.markdown 用于短摘要也可为空；完整精读笔记放 literature_note，避免重复。正文是 Markdown 字符串，支持 $行内公式$、$$独立公式$$、表格、Python 代码围栏、Mermaid 围栏。JSON 中换行写成 \n、LaTeX 反斜线写成 \\；确保可由 JSON.parse 解析。论文笔记请覆盖研究问题、核心创新、架构、数学推导、训练推理、实验、局限、复现、个人理解、启发和未解决问题；不要为填满模板而编造内容。

词汇的 title 为英文单词或短语；metadata.part_of_speech、sense 明确区分不同词性和词义，同一词义仅创建一次，将不同语境累积在 contextual_meaning、examples、translations、sources。数学知识按主题复用；算法描述与数学推导通过关系连接。科研想法保留假设、实验设计、风险和被否定原因，不把假设写成已验证结论。

状态枚举：paper=to_read/skimmed/reading/completed/archived；复现另用 metadata.reproduction_status=none/planned/in_progress/completed。idea=inspiration/survey/definition/design/experiment/analysis/writing/completed/paused/rejected；question=open/in_progress/resolved/paused；其余=learning/mastered。priority 和 importance 是 1–5，5 为最高；mastery 为 0–5。

完整 JSON Schema（这是软件模型生成的实际协议）：

```json
{
  "$defs": {
    "Entry": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "enum": [
            "paper",
            "vocabulary",
            "mathematics",
            "algorithm",
            "idea",
            "question"
          ],
          "title": "Kind",
          "type": "string"
        },
        "title": {
          "maxLength": 1000,
          "minLength": 1,
          "title": "Title",
          "type": "string"
        },
        "tags": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Tags",
          "type": "array"
        },
        "status": {
          "default": "",
          "title": "Status",
          "type": "string"
        },
        "metadata": {
          "$ref": "#/$defs/Metadata"
        },
        "markdown": {
          "default": "",
          "maxLength": 2000000,
          "title": "Markdown",
          "type": "string"
        },
        "key": {
          "pattern": "^[A-Za-z][A-Za-z0-9_-]{0,79}$",
          "title": "Key",
          "type": "string"
        },
        "match_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Match Id"
        }
      },
      "required": [
        "kind",
        "title",
        "key"
      ],
      "title": "Entry",
      "type": "object"
    },
    "ImportRelation": {
      "additionalProperties": false,
      "properties": {
        "source": {
          "title": "Source",
          "type": "string"
        },
        "target": {
          "title": "Target",
          "type": "string"
        },
        "type": {
          "default": "related_to",
          "enum": [
            "uses",
            "depends_on",
            "derived_from",
            "extends",
            "compares_with",
            "related_to",
            "prerequisite_of",
            "inspired_by",
            "validates",
            "contradicts"
          ],
          "title": "Type",
          "type": "string"
        },
        "description": {
          "default": "",
          "title": "Description",
          "type": "string"
        },
        "evidence": {
          "default": "",
          "title": "Evidence",
          "type": "string"
        }
      },
      "required": [
        "source",
        "target"
      ],
      "title": "ImportRelation",
      "type": "object"
    },
    "Metadata": {
      "additionalProperties": false,
      "properties": {
        "chinese_title": {
          "default": "",
          "title": "Chinese Title",
          "type": "string"
        },
        "english_name": {
          "default": "",
          "title": "English Name",
          "type": "string"
        },
        "abbreviation": {
          "default": "",
          "title": "Abbreviation",
          "type": "string"
        },
        "authors": {
          "items": {
            "type": "string"
          },
          "title": "Authors",
          "type": "array"
        },
        "institutions": {
          "items": {
            "type": "string"
          },
          "title": "Institutions",
          "type": "array"
        },
        "year": {
          "anyOf": [
            {
              "maximum": 2200,
              "minimum": 1800,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Year"
        },
        "venue": {
          "default": "",
          "title": "Venue",
          "type": "string"
        },
        "doi": {
          "default": "",
          "title": "Doi",
          "type": "string"
        },
        "arxiv_id": {
          "default": "",
          "title": "Arxiv Id",
          "type": "string"
        },
        "url": {
          "default": "",
          "title": "Url",
          "type": "string"
        },
        "project_url": {
          "default": "",
          "title": "Project Url",
          "type": "string"
        },
        "code_url": {
          "default": "",
          "title": "Code Url",
          "type": "string"
        },
        "abstract": {
          "default": "",
          "title": "Abstract",
          "type": "string"
        },
        "directions": {
          "items": {
            "type": "string"
          },
          "title": "Directions",
          "type": "array"
        },
        "keywords": {
          "items": {
            "type": "string"
          },
          "title": "Keywords",
          "type": "array"
        },
        "category_ids": {
          "items": {
            "type": "string"
          },
          "title": "Category Ids",
          "type": "array"
        },
        "reading_start": {
          "anyOf": [
            {
              "format": "date",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reading Start"
        },
        "reading_end": {
          "anyOf": [
            {
              "format": "date",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reading End"
        },
        "importance": {
          "default": 3,
          "maximum": 5,
          "minimum": 1,
          "title": "Importance",
          "type": "integer"
        },
        "priority": {
          "default": 3,
          "maximum": 5,
          "minimum": 1,
          "title": "Priority",
          "type": "integer"
        },
        "reproduction_status": {
          "default": "none",
          "enum": [
            "none",
            "planned",
            "in_progress",
            "completed"
          ],
          "title": "Reproduction Status",
          "type": "string"
        },
        "worth_reproducing": {
          "default": false,
          "title": "Worth Reproducing",
          "type": "boolean"
        },
        "reread": {
          "default": false,
          "title": "Reread",
          "type": "boolean"
        },
        "part_of_speech": {
          "default": "",
          "title": "Part Of Speech",
          "type": "string"
        },
        "sense": {
          "default": "",
          "title": "Sense",
          "type": "string"
        },
        "vocabulary_category": {
          "default": "general_academic",
          "enum": [
            "general_academic",
            "mathematical",
            "technical",
            "phrases",
            "writing"
          ],
          "title": "Vocabulary Category",
          "type": "string"
        },
        "meaning": {
          "default": "",
          "title": "Meaning",
          "type": "string"
        },
        "contextual_meaning": {
          "default": "",
          "title": "Contextual Meaning",
          "type": "string"
        },
        "collocations": {
          "items": {
            "type": "string"
          },
          "title": "Collocations",
          "type": "array"
        },
        "examples": {
          "items": {
            "type": "string"
          },
          "title": "Examples",
          "type": "array"
        },
        "translations": {
          "items": {
            "type": "string"
          },
          "title": "Translations",
          "type": "array"
        },
        "sources": {
          "description": "Free-text page/section/evidence; paper links use relations",
          "items": {
            "type": "string"
          },
          "title": "Sources",
          "type": "array"
        },
        "mastery": {
          "default": 0,
          "maximum": 5,
          "minimum": 0,
          "title": "Mastery",
          "type": "integer"
        },
        "textbooks": {
          "items": {
            "type": "string"
          },
          "title": "Textbooks",
          "type": "array"
        },
        "textbook_chapters": {
          "default": "",
          "title": "Textbook Chapters",
          "type": "string"
        },
        "idea_date": {
          "anyOf": [
            {
              "format": "date",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Idea Date"
        },
        "experiment_path": {
          "default": "",
          "title": "Experiment Path",
          "type": "string"
        },
        "next_action": {
          "default": "",
          "title": "Next Action",
          "type": "string"
        },
        "question_type": {
          "default": "research",
          "enum": [
            "english",
            "mathematics",
            "algorithm",
            "code",
            "experiment",
            "research"
          ],
          "title": "Question Type",
          "type": "string"
        },
        "resolved_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Resolved At"
        }
      },
      "title": "Metadata",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "schema_version": {
      "const": "1.0",
      "title": "Schema Version",
      "type": "string"
    },
    "paper": {
      "$ref": "#/$defs/Entry"
    },
    "literature_note": {
      "default": "",
      "maxLength": 2000000,
      "title": "Literature Note",
      "type": "string"
    },
    "vocabulary": {
      "items": {
        "$ref": "#/$defs/Entry"
      },
      "maxItems": 1000,
      "title": "Vocabulary",
      "type": "array"
    },
    "mathematics": {
      "items": {
        "$ref": "#/$defs/Entry"
      },
      "maxItems": 1000,
      "title": "Mathematics",
      "type": "array"
    },
    "algorithms": {
      "items": {
        "$ref": "#/$defs/Entry"
      },
      "maxItems": 1000,
      "title": "Algorithms",
      "type": "array"
    },
    "research_ideas": {
      "items": {
        "$ref": "#/$defs/Entry"
      },
      "maxItems": 1000,
      "title": "Research Ideas",
      "type": "array"
    },
    "questions": {
      "items": {
        "$ref": "#/$defs/Entry"
      },
      "maxItems": 1000,
      "title": "Questions",
      "type": "array"
    },
    "relations": {
      "items": {
        "$ref": "#/$defs/ImportRelation"
      },
      "maxItems": 5000,
      "title": "Relations",
      "type": "array"
    },
    "reading_summary": {
      "default": "",
      "maxLength": 100000,
      "title": "Reading Summary",
      "type": "string"
    }
  },
  "required": [
    "schema_version",
    "paper"
  ],
  "title": "ImportBundle",
  "type": "object",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:research-hub:reading-summary:1.0"
}
```
