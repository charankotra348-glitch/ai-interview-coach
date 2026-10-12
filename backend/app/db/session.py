import time
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and always close it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> float:
    """Run SELECT 1 and return the round-trip time in milliseconds."""
    start = time.perf_counter()

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    return (time.perf_counter() - start) * 1000
