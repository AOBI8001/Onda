"""SQLAlchemy persistence; SQLite locally, PostgreSQL through DATABASE_URL."""
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import DATABASE_URL


def uid(prefix=""):
    return prefix + uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Record(Base):
    """Versioned business aggregates. All writes go through domain services."""
    __tablename__ = "business_records"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    owner: Mapped[str] = mapped_column(String(80), index=True)
    merchant: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSON)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(20))
    merchant: Mapped[str] = mapped_column(String(80))
    expires: Mapped[str] = mapped_column(String(40))


class Proposal(Base):
    __tablename__ = "action_proposals"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    actor: Mapped[str] = mapped_column(String(80), index=True)
    role: Mapped[str] = mapped_column(String(20))
    merchant: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer)
    params: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created: Mapped[str] = mapped_column(String(40), default=now)
    expires: Mapped[str] = mapped_column(String(40))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    run_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)


class Thread(Base):
    __tablename__ = "chat_threads"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    actor: Mapped[str] = mapped_column(String(80), index=True)
    role: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(120))
    created: Mapped[str] = mapped_column(String(40), default=now)


class Message(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(80), index=True)
    role: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created: Mapped[str] = mapped_column(String(40), default=now)


class Run(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    actor: Mapped[str] = mapped_column(String(80), index=True)
    role: Mapped[str] = mapped_column(String(20))
    merchant: Mapped[str] = mapped_column(String(80))
    thread_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    prompt: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[str] = mapped_column(String(40), default=now)


class RunEvent(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(80), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    created: Mapped[str] = mapped_column(String(40), default=now)


class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    actor: Mapped[str] = mapped_column(String(80), index=True)
    merchant: Mapped[str] = mapped_column(String(80), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    created: Mapped[str] = mapped_column(String(40), default=now)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(80), index=True)
    actor: Mapped[str] = mapped_column(String(80))
    rating: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text)
    created: Mapped[str] = mapped_column(String(40), default=now)


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {}, pool_pre_ping=True)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_options(connection, _):
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")

Session = sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction():
    with Session.begin() as session:
        yield session
