"""Shared fixtures: in-memory SQLite, a frozen clock and a TestClient.

Environment variables are pinned BEFORE any ``app`` import so that
``app.config.settings`` never picks up demo values from ``backend/.env``
(e.g. ``HEART_REGEN_MINUTES=1``) and startup never touches the real DB.
"""

import os

os.environ["AUTO_SEED"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"
for _name, _value in {
    "MAX_HEARTS": "5",
    "HEART_REGEN_MINUTES": "30",
    "HEART_REFILL_GEM_COST": "350",
    "BASE_LESSON_XP": "10",
    "PERFECT_BONUS_XP": "5",
    "PRACTICE_XP": "5",
    "DEFAULT_DAILY_GOAL_XP": "20",
    "APP_TIMEZONE": "Asia/Kolkata",
    "DEMO_USERNAME": "arnav",
}.items():
    os.environ[_name] = _value

import warnings  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

import pytest  # noqa: E402

# Upstream notice from Starlette's TestClient; not actionable in this project.
warnings.filterwarnings("ignore", message=r"Using `httpx` with `starlette\.testclient`")
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401  (registers tables on Base.metadata)
from app.database import Base, get_db  # noqa: E402
from app.deps import get_now  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

# Naive UTC, like everything stored in the DB. 06:30 UTC = 12:00 in Asia/Kolkata.
FIXED_NOW = datetime(2026, 1, 15, 6, 30)


class FrozenClock:
    """Mutable fixed clock served to the app through the ``get_now`` override."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def advance(self, **kwargs: float) -> datetime:
        self.now = self.now + timedelta(**kwargs)
        return self.now

    def set(self, now: datetime) -> None:
        self.now = now


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    # Mirrors app.database.SessionLocal.
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded_db(db):
    seed(db, now=FIXED_NOW)
    return db


@pytest.fixture
def clock():
    return FrozenClock(FIXED_NOW)


@pytest.fixture
def client(session_factory, clock):
    """TestClient without the context manager: lifespan (auto-seed) never runs."""

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_now] = lambda: clock.now
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def api(client, seeded_db):
    """Client over a seeded DB (the usual starting point for API tests)."""
    return client
