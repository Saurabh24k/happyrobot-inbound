from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON  

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow, index=True)

    event: str = Field(index=True)                 # "booked", "no-agreement", etc.
    session_id: Optional[str] = Field(default=None, index=True)

    mc: Optional[str] = Field(default=None, index=True)
    load_id: Optional[str] = Field(default=None, index=True)
    sentiment: Optional[str] = Field(default=None, index=True)
    rounds: Optional[int] = Field(default=None)

    agreed_rate: Optional[float] = Field(default=None)
    loadboard_rate: Optional[float] = Field(default=None)
    equipment_type: Optional[str] = Field(default=None, index=True)

    # Explicit SQLAlchemy JSON column avoids SQLModel’s type inference issue
    extra: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
