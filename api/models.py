# api/models.py
from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON

# Keep everything as simple types (str/int/float/bool) — no Python Enum types.
# JSON columns work on Postgres and SQLite with this generic SQLAlchemy JSON.

class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)

    event: str = Field(index=True)                 # 'booked', 'no-agreement', etc.
    session_id: Optional[str] = Field(default=None, index=True)

    mc: Optional[str] = Field(default=None, index=True)
    load_id: Optional[str] = Field(default=None, index=True)
    sentiment: Optional[str] = Field(default=None, index=True)  # 'positive' | 'neutral' | 'negative'
    rounds: Optional[int] = None

    agreed_rate: Optional[float] = None
    loadboard_rate: Optional[float] = None
    equipment_type: Optional[str] = Field(default=None, index=True)

    # free-form payload for auditing/troubleshooting
    extra: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class Offer(SQLModel, table=True):
    __tablename__ = "offers"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)

    who: str  # 'carrier' | 'agent'
    value: float

    t: datetime = Field(default_factory=datetime.utcnow, index=True)


class ToolCall(SQLModel, table=True):
    __tablename__ = "tool_calls"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)

    fn: str                   # 'verify_mc' | 'search_loads' | 'evaluate_offer' | ...
    ok: Optional[bool] = None # True/False/None
    info: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class Utterance(SQLModel, table=True):
    __tablename__ = "utterances"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)

    role: str   # 'user' | 'assistant'
    text: str

    t: datetime = Field(default_factory=datetime.utcnow, index=True)
