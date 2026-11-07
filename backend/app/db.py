"""
Database setup and table definitions (SQLAlchemy 2.0 style, SQLite file).

Each Python class below is one table. Each `Mapped[...] = mapped_column(...)`
line is one column. SQLAlchemy turns these classes into real SQL tables.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import DATABASE_URL

# ---------------------------------------------------------------------------
# 1. Connection setup
# ---------------------------------------------------------------------------

# The engine is the app's single "connection factory" to the database.
# check_same_thread=False: by default SQLite refuses to let a connection made in
# one thread be used in another. FastAPI runs normal (non-async) routes in a pool
# of worker threads, so a request may use a connection created on another
# thread. Each request gets its own session (see get_db), so this is safe.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# SQLite IGNORES foreign keys unless you switch them on, for every new connection.
# This listener runs each time the engine opens a connection and turns them on,
# so the database really blocks bad ids and really does the CASCADE deletes.
@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# sessionmaker builds a "session factory". Calling SessionLocal() gives one
# Session: a short conversation with the database (queries, adds, commit).
SessionLocal = sessionmaker(bind=engine)


# Every table class inherits from Base, so Base knows about all our tables.
class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    """Current time in UTC. We always store UTC so times never depend on where
    the server is. (SQLite drops the timezone label when saving, so times read
    back look 'naive', but we know they are UTC.)"""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 2. Tables
# ondelete="CASCADE" means: when the parent row is deleted, the database also
# deletes the child rows. Example: delete a session -> its questions go too.
# ---------------------------------------------------------------------------

class Repo(Base):
    """One indexed GitHub repository."""
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    github_url: Mapped[str] = mapped_column(String(500))
    name: Mapped[str] = mapped_column(String(200))
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # AI summary (Phase 4)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Chunk(Base):
    """One function/class/file-level piece of code. Only the metadata lives here;
    the code text and its embedding live in ChromaDB (Phase 3)."""
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(String(500))
    name: Mapped[str] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(String(20))  # function / class / component / route / file
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    importance_score: Mapped[float] = mapped_column(Float, default=0.0)


class InterviewSession(Base):
    """One interview. Named InterviewSession (not Session) because SQLAlchemy
    already has a class called Session (the database conversation from
    SessionLocal). Two classes with the same name would be very confusing."""
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(20))  # beginner / intermediate / advanced
    num_questions: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="NOT_STARTED")
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Question(Base):
    """One question asked in a session (a main question or a follow-up)."""
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    # SET NULL (not CASCADE): if a chunk is removed, e.g. when a repo is
    # re-indexed, we keep the old question for history and just lose the link.
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True)
    # Self-referencing foreign key: points to ANOTHER row in this same table.
    # A follow-up stores the id of the question it follows. Main questions have NULL.
    parent_question_id: Mapped[int | None] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(20))  # what / why / what_if / follow_up
    text: Mapped[str] = mapped_column(Text)
    ideal_points_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    order_no: Mapped[int] = mapped_column(Integer)


class Answer(Base):
    """The student's answer to one question, plus its scores and speech stats."""
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    transcript: Mapped[str] = mapped_column(Text)
    # Everything below is empty (NULL) until we have it, e.g. no audio in text mode.
    audio_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    wpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    filler_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correctness: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-4
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-3
    clarity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-3
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    missed_points_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


# ---------------------------------------------------------------------------
# 3. Helpers used by main.py
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create any tables that don't exist yet. It does NOT change tables that
    already exist, so after changing a table during development, delete
    repoviva.db and restart the server."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: gives each request its own database session.

    `yield` hands the session to the route and pauses here. When the route has
    finished (even if it crashed), the code continues into `finally` and closes
    the session, so connections are never leaked."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
