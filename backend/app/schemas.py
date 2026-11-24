"""Typed metadata and the single source of truth for interchange v1."""
import unicodedata
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

Kind = Literal['paper', 'vocabulary', 'mathematics', 'algorithm', 'idea', 'question']
RelationType = Literal['uses', 'depends_on', 'derived_from', 'extends', 'compares_with', 'related_to', 'prerequisite_of', 'inspired_by', 'validates', 'contradicts']
KINDS = ['paper', 'vocabulary', 'mathematics', 'algorithm', 'idea', 'question']
SYMMETRIC = {'related_to', 'compares_with'}
PAPER_STATES = ['to_read', 'skimmed', 'reading', 'completed', 'archived']
IDEA_STATES = ['inspiration', 'survey', 'definition', 'design', 'experiment', 'analysis', 'writing', 'completed', 'paused', 'rejected']
QUESTION_STATES = ['open', 'in_progress', 'resolved', 'paused']

def normalize(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Metadata(Strict):
    chinese_title: str = ''
    english_name: str = ''
    abbreviation: str = ''
    authors: list[str] = Field(default_factory=list)
    institutions: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1800, le=2200)
    venue: str = ''
    doi: str = ''
    arxiv_id: str = ''
    url: str = ''
    project_url: str = ''
    code_url: str = ''
    abstract: str = ''
    directions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    category_ids: list[str] = Field(default_factory=list)
    reading_start: date | None = None
    reading_end: date | None = None
    importance: int = Field(default=3, ge=1, le=5)
    priority: int = Field(default=3, ge=1, le=5)
    reproduction_status: Literal['none', 'planned', 'in_progress', 'completed'] = 'none'
    worth_reproducing: bool = False
    reread: bool = False
    part_of_speech: str = ''
    sense: str = ''
    vocabulary_category: Literal['general_academic', 'mathematical', 'technical', 'phrases', 'writing'] = 'general_academic'
    meaning: str = ''
    contextual_meaning: str = ''
    collocations: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    translations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list, description='Free-text page/section/evidence; paper links use relations')
    mastery: int = Field(default=0, ge=0, le=5)
    textbooks: list[str] = Field(default_factory=list)
    textbook_chapters: str = ''
    idea_date: date | None = None
    experiment_path: str = ''
    next_action: str = ''
    question_type: Literal['english', 'mathematics', 'algorithm', 'code', 'experiment', 'research'] = 'research'
    resolved_at: str | None = None

DEFAULTS = {'paper':'to_read','vocabulary':'learning','mathematics':'learning','algorithm':'learning','idea':'inspiration','question':'open'}
STATES = {'paper':PAPER_STATES, 'idea':IDEA_STATES, 'question':QUESTION_STATES, 'vocabulary':['learning','mastered'], 'mathematics':['learning','mastered'], 'algorithm':['learning','mastered']}

class NodeInput(Strict):
    kind: Kind
    title: str = Field(min_length=1, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    status: str = ''
    metadata: Metadata = Field(default_factory=Metadata)
    markdown: str = Field(default='', max_length=2_000_000)

    @model_validator(mode='after')
    def valid(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError('标题不能为空')
        self.status = self.status or DEFAULTS[self.kind]
        if self.status not in STATES[self.kind]:
            raise ValueError(f'{self.kind} 无效状态: {self.status}')
        self.tags = list(dict.fromkeys(t.strip() for t in self.tags if t.strip()))
        return self

class NodeUpdate(NodeInput):
    expected_version: int = Field(ge=1)

class Entry(NodeInput):
    key: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,79}$')
    match_id: str | None = None

class ImportRelation(Strict):
    source: str
    target: str
    type: RelationType = 'related_to'
    description: str = ''
    evidence: str = ''

class ImportBundle(Strict):
    schema_version: Literal['1.0']
    paper: Entry
    literature_note: str = Field(default='', max_length=2_000_000)
    vocabulary: list[Entry] = Field(default_factory=list, max_length=1000)
    mathematics: list[Entry] = Field(default_factory=list, max_length=1000)
    algorithms: list[Entry] = Field(default_factory=list, max_length=1000)
    research_ideas: list[Entry] = Field(default_factory=list, max_length=1000)
    questions: list[Entry] = Field(default_factory=list, max_length=1000)
    relations: list[ImportRelation] = Field(default_factory=list, max_length=5000)
    reading_summary: str = Field(default='', max_length=100000)

    def entries(self):
        return [self.paper, *self.vocabulary, *self.mathematics, *self.algorithms, *self.research_ideas, *self.questions]

    @model_validator(mode='after')
    def references(self):
        for entries, kind in [([self.paper],'paper'),(self.vocabulary,'vocabulary'),(self.mathematics,'mathematics'),(self.algorithms,'algorithm'),(self.research_ideas,'idea'),(self.questions,'question')]:
            if any(e.kind != kind for e in entries):
                raise ValueError(f'集合的 kind 必须为 {kind}')
        keys = [e.key for e in self.entries()]
        if len(keys) != len(set(keys)):
            raise ValueError('条目 key 不得重复')
        for r in self.relations:
            if r.source not in keys or r.target not in keys or r.source == r.target:
                raise ValueError('关联必须引用本次导入中不同条目的 key')
        return self

class Decision(Strict):
    action: Literal['new','merge','skip']
    target_id: str | None = None
    expected_version: int | None = None

class ImportCommit(Strict):
    bundle: ImportBundle
    decisions: dict[str, Decision]

class RelationInput(Strict):
    source: str
    target: str
    type: RelationType
    description: str = ''
    evidence: str = ''

class ReviewInput(Strict):
    rating: Literal['again','hard','good','easy']
    expected_version: int = Field(ge=1)

class MergeInput(Strict):
    source_id: str
    target_id: str
    source_version: int = Field(ge=1)
    target_version: int = Field(ge=1)

class CategoryInput(Strict):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal['mathematics','algorithm']
    parent_id: str | None = None
