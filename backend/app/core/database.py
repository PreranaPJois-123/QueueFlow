from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

from sqlalchemy.pool import StaticPool

if settings.sync_database_url.startswith("sqlite"):
    engine = create_engine(
        settings.sync_database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        settings.sync_database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
        connect_args={"connect_timeout": 5},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
