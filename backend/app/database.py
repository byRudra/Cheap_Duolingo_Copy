from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite ignores foreign keys unless this pragma is set on every connection."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def serialize_sqlite_writes(target: Engine) -> None:
    """Start every transaction with BEGIN IMMEDIATE (SQLAlchemy's pysqlite recipe).

    Requests read the user row and then write absolute values (hearts, XP,
    streak). Taking SQLite's write lock before the first read serializes those
    read-modify-write cycles, so parallel wrong answers can't each read
    ``hearts=5`` and all write 4.
    """

    @event.listens_for(target, "connect")
    def _disable_implicit_begin(dbapi_connection, _connection_record) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(target, "begin")
    def _begin_immediate(conn) -> None:
        conn.exec_driver_sql("BEGIN IMMEDIATE")


engine = create_engine(
    settings.resolved_database_url,
    connect_args={"check_same_thread": False, "timeout": 15},
)
if engine.dialect.name == "sqlite":
    serialize_sqlite_writes(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
