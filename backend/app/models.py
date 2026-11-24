from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Node(Base):
    __tablename__ = 'nodes'
    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False, index=True)
    title = Column(Text, nullable=False)
    normalized_title = Column(Text, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    tags_json = Column(Text, nullable=False, default='[]')
    metadata_json = Column(Text, nullable=False, default='{}')
    note_path = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False, index=True)
    deleted = Column(Boolean, nullable=False, default=False, index=True)

class Revision(Base):
    __tablename__ = 'revisions'
    id = Column(String, primary_key=True)
    node_id = Column(String, ForeignKey('nodes.id'), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    note_path = Column(Text, nullable=False)
    snapshot = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint('node_id','version'),)

class Relation(Base):
    __tablename__ = 'relations'
    id = Column(String, primary_key=True)
    source = Column(String, ForeignKey('nodes.id'), nullable=False, index=True)
    target = Column(String, ForeignKey('nodes.id'), nullable=False, index=True)
    type = Column(String, nullable=False)
    description = Column(Text, nullable=False, default='')
    evidence = Column(Text, nullable=False, default='')
    created_at = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint('source','target','type'),)

class Attachment(Base):
    __tablename__ = 'attachments'
    id = Column(String, primary_key=True)
    node_id = Column(String, ForeignKey('nodes.id'), nullable=False, index=True)
    name = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    media_type = Column(String, nullable=False)
    sha256 = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    created_at = Column(String, nullable=False)

class ReviewState(Base):
    __tablename__ = 'review_states'
    node_id = Column(String, ForeignKey('nodes.id'), primary_key=True)
    repetitions = Column(Integer, nullable=False, default=0)
    interval_days = Column(Integer, nullable=False, default=0)
    ease = Column(String, nullable=False, default='2.5')
    due_at = Column(String, nullable=False)
    last_review = Column(String)
    lapses = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)

class ReviewLog(Base):
    __tablename__ = 'review_logs'
    id = Column(String, primary_key=True)
    node_id = Column(String, ForeignKey('nodes.id'), nullable=False, index=True)
    rating = Column(String, nullable=False)
    reviewed_at = Column(String, nullable=False)
    before_json = Column(Text, nullable=False)
    after_json = Column(Text, nullable=False)
    algorithm = Column(String, nullable=False, default='sm2-v1')

class ImportReceipt(Base):
    __tablename__ = 'import_receipts'
    digest = Column(String, primary_key=True)
    report_json = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)

class Category(Base):
    __tablename__ = 'categories'
    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False)
    name = Column(String, nullable=False)
    parent_id = Column(String, ForeignKey('categories.id'))
