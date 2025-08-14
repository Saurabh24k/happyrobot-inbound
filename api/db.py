import os
from sqlmodel import SQLModel, create_engine, Session

def _normalize(url: str) -> str:
    # Render often provides postgres://; SQLAlchemy wants postgresql+psycopg2://
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url

DATABASE_URL = _normalize(os.getenv("DATABASE_URL", "sqlite:///./events.db"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    return Session(engine)
