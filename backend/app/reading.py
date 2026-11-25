"""Local reading provenance. Coordinates are PDF user-space points, never screen pixels."""
import hashlib
import json
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import select, or_
from .models import SourceAnchor, SourceLink, Annotation, AnnotationRevision, PaperReadingState, Attachment, Node, Relation, ReviewState
from .schemas import Strict, NodeInput, Entry
from .services import get_node, node_dict, save_node, check_version, merge_data, candidates, add_relation, state_dict
from .workspace import uid, now, dumps


class PageRect(Strict):
    page: int = Field(ge=1, le=100000)
    rect: tuple[float, float, float, float]

    @model_validator(mode='after')
    def valid(self):
        import math
        x0, y0, x1, y1 = self.rect
        if not all(math.isfinite(v) and abs(v) <= 1000000 for v in self.rect) or x1 <= x0 or y1 <= y0:
            raise ValueError('选区必须是有限、非空的 PDF 坐标矩形')
        return self


class AnchorInput(Strict):
    paper_id: str
    attachment_id: str
    pdf_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    page: int = Field(ge=1, le=100000)
    printed_page: str = Field(default='', max_length=200)
    raw_text: str = Field(min_length=1, max_length=200000)
    cleaned_text: str = Field(min_length=1, max_length=200000)
    context: str = Field(default='', max_length=200000)
    section: str = Field(default='', max_length=2000)
    rects: list[PageRect] = Field(min_length=1, max_length=2048)
    notes: str = Field(default='', max_length=100000)

    @model_validator(mode='after')
    def valid(self):
        if self.page != min(r.page for r in self.rects):
            raise ValueError('来源页码必须等于选区的起始文件页码（从 1 开始）')
        if not self.raw_text.strip() or not self.cleaned_text.strip():
            raise ValueError('原文不能为空')
        return self


class AnnotationInput(Strict):
    color: str = Field(default='#e6cb73', pattern=r'^#[a-fA-F0-9]{6}$')
    label: str = Field(default='重要内容', max_length=200)
    markdown: str = Field(default='', max_length=500000)
    expected_version: int = Field(default=0, ge=0)


class CaptureInput(Strict):
    anchor: AnchorInput | None = None
    anchor_id: str | None = None
    node: NodeInput
    mode: Literal['new', 'append', 'edit'] = 'new'
    target_id: str | None = None
    expected_version: int | None = Field(default=None, ge=1)
    provenance: Literal['paper', 'personal', 'ai', 'external'] = 'personal'
    annotation: AnnotationInput | None = None

    @model_validator(mode='after')
    def valid(self):
        if (self.anchor is None) == (self.anchor_id is None):
            raise ValueError('必须且只能指定一个原文来源')
        if self.node.kind == 'paper':
            raise ValueError('论文笔记通过原文插入功能保存')
        if self.mode != 'new' and (not self.target_id or self.expected_version is None):
            raise ValueError('关联或编辑已有条目必须提供目标和版本')
        return self


class LinkInput(Strict):
    node_id: str


class ReadingWorkspaceInput(Strict):
    mode: Literal['note', 'pdf', 'split'] = 'note'
    split_width: int = Field(default=55, ge=25, le=75)
    panel_tab: Literal['notes', 'annotations', 'vocabulary', 'mathematics', 'algorithm', 'idea', 'question'] = 'notes'
    selected_anchor: str = Field(default='', max_length=100)
    selected_node: str = Field(default='', max_length=100)
    attachment_id: str = Field(default='', max_length=100)
    draft: dict | None = None

    @model_validator(mode='after')
    def valid(self):
        if len(dumps(self.draft).encode()) > 2500000:
            raise ValueError('快速录入草稿超过 2.5 MB，请下载后整理')
        return self


def eligible_vocabulary(n):
    """A collected word has no flashcard answer until a meaning is supplied."""
    m = json.loads(n.metadata_json)
    return n.kind == 'vocabulary' and bool((m.get('meaning') or '').strip() or (m.get('contextual_meaning') or '').strip())


def attachment_for(s, paper_id, attachment_id):
    paper = get_node(s, paper_id)
    a = s.get(Attachment, attachment_id)
    if paper.kind != 'paper' or not a or a.node_id != paper.id or a.media_type != 'application/pdf':
        raise HTTPException(422, '来源必须是当前论文的 PDF 附件')
    return a


def verify_file(ws, attachment, expected):
    if attachment.sha256 != expected:
        raise HTTPException(409, 'PDF 文件版本已变化。旧来源已保留，请在正确文件中重新定位。')
    path = ws.path(attachment.path)
    if not path.is_file():
        raise HTTPException(409, '来源 PDF 文件缺失。请恢复原附件后再定位。')
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise HTTPException(409, 'PDF 内容与保存的版本不符，已阻止应用旧坐标。请恢复原文件或重新定位。')


def get_anchor(s, anchor_id):
    a = s.get(SourceAnchor, anchor_id)
    if not a or a.deleted:
        raise HTTPException(404, '原文定位不存在或已删除')
    get_node(s, a.paper_id)
    return a


def create_anchor(s, ws, data):
    attachment = attachment_for(s, data.paper_id, data.attachment_id)
    verify_file(ws, attachment, data.pdf_sha256)
    values = data.model_dump(exclude={'rects'})
    anchor = SourceAnchor(id=uid(), **values, rects_json=dumps([r.model_dump() for r in data.rects]),
                          version=1, deleted=False, created_at=now(), updated_at=now())
    s.add(anchor)
    s.flush()
    return anchor


def annotation_dict(ws, a):
    return {**{k: getattr(a, k) for k in ['id', 'anchor_id', 'color', 'label', 'version', 'deleted', 'created_at', 'updated_at']}, 'markdown': ws.read_note(a.note_path)}


def anchor_dict(s, ws, a, include_nodes=True):
    result = {k: getattr(a, k) for k in ['id', 'paper_id', 'attachment_id', 'pdf_sha256', 'page', 'printed_page', 'raw_text',
                                       'cleaned_text', 'context', 'section', 'notes', 'version', 'deleted', 'created_at', 'updated_at']}
    result['rects'] = json.loads(a.rects_json)
    paper = s.get(Node, a.paper_id)
    attachment = s.get(Attachment, a.attachment_id)
    result['paper_title'] = paper.title if paper else '来源论文缺失'
    result['available'] = bool(paper and not paper.deleted and attachment and attachment.sha256 == a.pdf_sha256 and ws.path(attachment.path).is_file())
    annotation = s.scalar(select(Annotation).where(Annotation.anchor_id == a.id))
    result['annotation'] = annotation_dict(ws, annotation) if annotation and not annotation.deleted else None
    result['annotation_revision'] = annotation.version if annotation else 0
    if include_nodes:
        result['nodes'] = [node_dict(n) for n in s.scalars(select(Node).join(SourceLink, SourceLink.node_id == Node.id)
                          .where(SourceLink.anchor_id == a.id, Node.deleted == False))]
    return result


def link_source(s, a, node_id):
    get_node(s, node_id)
    if not s.get(SourceLink, (a.id, node_id)):
        s.add(SourceLink(anchor_id=a.id, node_id=node_id, created_at=now()))
    s.flush()


def save_annotation(s, ws, a, data):
    old = s.scalar(select(Annotation).where(Annotation.anchor_id == a.id))
    if old:
        check_version(old, data.expected_version)
    else:
        if data.expected_version != 0:
            raise HTTPException(409, '批注版本已变化，请刷新')
        old = Annotation(id=uid(), anchor_id=a.id, version=0, created_at=now())
        s.add(old)
    old.color, old.label = data.color, data.label
    old.deleted, old.updated_at, old.version = False, now(), old.version + 1
    old.note_path = ws.write_note('annotation', old.id, old.version, data.markdown)
    s.flush()
    s.add(AnnotationRevision(id=uid(), annotation_id=old.id, version=old.version, note_path=old.note_path,
                            snapshot=dumps({'color':old.color,'label':old.label}), created_at=now()))
    s.flush()
    return old


def reading_export(s, ws):
    def rows(model):
        return [{col.name: getattr(r, col.name) for col in model.__table__.columns} for r in s.scalars(select(model))]
    return {'source_anchors': rows(SourceAnchor), 'source_links': rows(SourceLink), 'annotations': [dict(row, markdown=ws.read_note(row['note_path'])) for row in rows(Annotation)],
            'annotation_revisions': [dict(row, markdown=ws.read_note(row['note_path'])) for row in rows(AnnotationRevision)],
            'paper_reading_states': rows(PaperReadingState), 'reading_data_version': '1.0'}


def reading_router(ws):
    r = APIRouter(prefix='/api')

    @r.get('/attachments/{attachment_id}/integrity')
    def attachment_integrity(attachment_id: str, sha256: str):
        with ws.lock, ws.Session() as s:
            a = s.get(Attachment, attachment_id)
            if not a:
                raise HTTPException(404, 'PDF 不存在')
            get_node(s, a.node_id)
            verify_file(ws, a, sha256)
            return {'verified': True, 'sha256': a.sha256}

    @r.post('/sources', status_code=201)
    def source_create(data: AnchorInput):
        with ws.lock, ws.Session.begin() as s:
            return anchor_dict(s, ws, create_anchor(s, ws, data))

    @r.get('/sources/{anchor_id}')
    def source_resolve(anchor_id: str):
        with ws.lock, ws.Session() as s:
            a = get_anchor(s, anchor_id)
            attachment = attachment_for(s, a.paper_id, a.attachment_id)
            verify_file(ws, attachment, a.pdf_sha256)
            return anchor_dict(s, ws, a)

    @r.delete('/sources/{anchor_id}')
    def source_delete(anchor_id: str, expected_version: int = Query(ge=1)):
        with ws.lock, ws.Session.begin() as s:
            a = get_anchor(s, anchor_id)
            check_version(a, expected_version)
            a.deleted, a.version, a.updated_at = True, a.version + 1, now()
            return {'deleted': True, 'knowledge_preserved': True}

    @r.post('/sources/{anchor_id}/links')
    def source_link(anchor_id: str, data: LinkInput):
        with ws.lock, ws.Session.begin() as s:
            a = get_anchor(s, anchor_id)
            link_source(s, a, data.node_id)
            return anchor_dict(s, ws, a)

    @r.delete('/sources/{anchor_id}/links/{node_id}')
    def source_unlink(anchor_id: str, node_id: str):
        with ws.lock, ws.Session.begin() as s:
            get_anchor(s, anchor_id)
            link = s.get(SourceLink, (anchor_id, node_id))
            if link:
                s.delete(link)
            return {'unlinked': True, 'knowledge_preserved': True}

    @r.put('/sources/{anchor_id}/annotation')
    def annotation_save(anchor_id: str, data: AnnotationInput):
        with ws.lock, ws.Session.begin() as s:
            a = get_anchor(s, anchor_id)
            return annotation_dict(ws, save_annotation(s, ws, a, data))

    @r.delete('/sources/{anchor_id}/annotation')
    def annotation_delete(anchor_id: str, expected_version: int = Query(ge=1)):
        with ws.lock, ws.Session.begin() as s:
            get_anchor(s, anchor_id)
            old = s.scalar(select(Annotation).where(Annotation.anchor_id == anchor_id, Annotation.deleted == False))
            if not old:
                raise HTTPException(404, '批注不存在')
            check_version(old, expected_version)
            old.deleted, old.version, old.updated_at = True, old.version + 1, now()
            return {'deleted': True, 'sources_preserved': True, 'knowledge_preserved': True}

    @r.get('/nodes/{node_id}/sources')
    def node_sources(node_id: str):
        with ws.lock, ws.Session() as s:
            get_node(s, node_id)
            return [anchor_dict(s, ws, a) for a in s.scalars(select(SourceAnchor)
                    .join(SourceLink, SourceLink.anchor_id == SourceAnchor.id)
                    .join(Node, Node.id == SourceAnchor.paper_id)
                    .where(SourceLink.node_id == node_id, SourceAnchor.deleted == False, Node.deleted == False)
                    .order_by(SourceAnchor.created_at.desc()))]

    @r.post('/reading/candidates')
    def capture_candidates(data: NodeInput):
        with ws.lock, ws.Session() as s:
            matches = candidates(s, Entry(**data.model_dump(), key='capture'))
            for n in matches:
                n['review'] = state_dict(s.get(ReviewState, n['id'])) if n['kind'] == 'vocabulary' else None
                n['sources'] = [anchor_dict(s, ws, a, False) for a in s.scalars(select(SourceAnchor)
                    .join(SourceLink, SourceLink.anchor_id == SourceAnchor.id)
                    .where(SourceLink.node_id == n['id'], SourceAnchor.deleted == False))]
            return matches

    @r.post('/reading/capture', status_code=201)
    def capture(data: CaptureInput):
        with ws.lock, ws.Session.begin() as s:
            old = None
            if data.mode != 'new':
                old = get_node(s, data.target_id)
                if old.kind != data.node.kind:
                    raise HTTPException(422, '目标知识类型不同')
                check_version(old, data.expected_version)
            a = get_anchor(s, data.anchor_id) if data.anchor_id else create_anchor(s, ws, data.anchor)
            attachment = attachment_for(s, a.paper_id, a.attachment_id)
            if data.anchor_id:
                verify_file(ws, attachment, a.pdf_sha256)
            origin = {'paper': '论文原文摘录（解释需核对原文）', 'personal': '用户个人笔记', 'ai': 'AI 辅助解释（未经论文作者确认）', 'external': '外部参考资料'}[data.provenance]
            quote = '\n'.join('> ' + line for line in a.raw_text.splitlines())
            citation = f'\n\n### 原文出处 · PDF 第 {a.page} 页\n\n{quote}\n\n[返回论文原文 · 第 {a.page} 页](#source/{a.id})'
            incoming = data.node.model_copy(update={'markdown': '## ' + origin + '\n\n' + data.node.markdown + citation})
            if old and data.mode == 'append':
                value = merge_data(ws, old, incoming)
            else:
                value = incoming
                if old:
                    # Lifecycle and tags are edited in the ordinary detail view, not this quick form.
                    value = value.model_copy(update={'status':old.status,'tags':json.loads(old.tags_json)})
            n = save_node(s, ws, value, old)
            link_source(s, a, n.id)
            add_relation(s, n.id, a.paper_id, 'inspired_by' if n.kind == 'idea' else 'derived_from', '阅读时收集', f'PDF 第 {a.page} 页 · {a.id}')
            if data.annotation:
                save_annotation(s, ws, a, data.annotation)
            return {'node': node_dict(n, ws), 'source': anchor_dict(s, ws, a)}

    @r.get('/reading/incomplete-vocabulary')
    def incomplete():
        with ws.lock, ws.Session() as s:
            return [node_dict(n) for n in s.scalars(select(Node).where(Node.kind == 'vocabulary', Node.deleted == False)) if not eligible_vocabulary(n)]

    @r.get('/papers/{paper_id}/reading')
    def paper_reading(paper_id: str):
        with ws.lock, ws.Session() as s:
            if get_node(s, paper_id).kind != 'paper':
                raise HTTPException(422, '需要论文条目')
            anchors = list(s.scalars(select(SourceAnchor).where(SourceAnchor.paper_id == paper_id, SourceAnchor.deleted == False).order_by(SourceAnchor.page, SourceAnchor.created_at)))
            ids = set(s.scalars(select(SourceLink.node_id).where(SourceLink.anchor_id.in_([a.id for a in anchors]))))
            relations = list(s.scalars(select(Relation).where(or_(Relation.source == paper_id, Relation.target == paper_id))))
            ids.update(rel.target if rel.source == paper_id else rel.source for rel in relations)
            nodes = list(s.scalars(select(Node).where(Node.id.in_(ids), Node.deleted == False)))
            return {'sources': [anchor_dict(s, ws, a) for a in anchors], 'nodes': [node_dict(n) for n in nodes]}

    @r.post('/papers/{paper_id}/links')
    def paper_link(paper_id: str, data: LinkInput):
        with ws.lock, ws.Session.begin() as s:
            if get_node(s, paper_id).kind != 'paper':
                raise HTTPException(422, '需要论文条目')
            add_relation(s, data.node_id, paper_id, 'related_to', '阅读面板手动关联')
            return {'linked': True}

    @r.delete('/papers/{paper_id}/links/{node_id}')
    def paper_unlink(paper_id: str, node_id: str):
        with ws.lock, ws.Session.begin() as s:
            get_node(s, paper_id)
            get_node(s, node_id)
            for link in s.scalars(select(SourceLink).join(SourceAnchor, SourceAnchor.id == SourceLink.anchor_id)
                    .where(SourceAnchor.paper_id == paper_id, SourceLink.node_id == node_id)):
                s.delete(link)
            for rel in s.scalars(select(Relation).where(or_(
                    (Relation.source == paper_id) & (Relation.target == node_id),
                    (Relation.target == paper_id) & (Relation.source == node_id)))):
                s.delete(rel)
            return {'unlinked': True, 'knowledge_preserved': True}

    @r.get('/papers/{paper_id}/reading-workspace')
    def workspace_get(paper_id: str):
        with ws.lock, ws.Session() as s:
            get_node(s, paper_id)
            state = s.get(PaperReadingState, paper_id)
            return json.loads(state.data_json) if state else ReadingWorkspaceInput().model_dump()

    @r.put('/papers/{paper_id}/reading-workspace')
    def workspace_save(paper_id: str, data: ReadingWorkspaceInput):
        with ws.lock, ws.Session.begin() as s:
            if get_node(s, paper_id).kind != 'paper':
                raise HTTPException(422, '需要论文条目')
            if data.attachment_id:
                attachment_for(s, paper_id, data.attachment_id)
            state = s.get(PaperReadingState, paper_id)
            if not state:
                state = PaperReadingState(paper_id=paper_id)
                s.add(state)
            state.data_json, state.updated_at = dumps(data.model_dump()), now()
            return data.model_dump()

    return r
