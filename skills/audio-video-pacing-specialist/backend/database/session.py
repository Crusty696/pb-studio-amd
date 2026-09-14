"""Database Session Factory."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

engine = create_engine(
    f"sqlite:///{os.path.join(os.path.dirname(__file__), '..', 'pacing_app.db')}",
    echo=False,  # Set to True for debugging
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_session():
    """Get a new database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize the database with tables."""
    from backend.database.models import Base
    Base.metadata.create_all(bind=engine)
