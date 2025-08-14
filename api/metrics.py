from __future__ import annotations
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter
from sqlalchemy import text
from sqlmodel import Session

from .db import engine, get_session
from .models import Event

DB_STORAGE_LIMIT_BYTES = int(os.getenv("DB_STORAGE_LIMIT_BYTES", str(1024 * 1024 * 1024)))

def _pg_usage(session: Session) -> Dict[str, Any]:
    # database name
    name_row = session.exec(text("SELECT current_database() AS name")).first()
    dbname = (name_row or {"name": None})["name"]

    # database size
    size_row = session.exec(
        text("SELECT pg_database_size(current_database()) AS bytes")
    ).first()
    used_bytes = int((size_row or {"bytes": 0})["bytes"])

    # table sizes + row estimates
    rows = session.exec(
        text("""
            SELECT
              c.relname AS name,
              pg_total_relation_size(c.oid) AS size_bytes,
              COALESCE(s.n_live_tup, 0) AS rows
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema')
            ORDER BY size_bytes DESC
        """)
    ).all()

    tables: List[Dict[str, Any]] = []
    for r in rows or []:
        tables.append({
            "name": r["name"],
            "rows": int(r["rows"]),
            "size_bytes": int(r["size_bytes"]),
            "size_pretty": _pretty_bytes(int(r["size_bytes"])),
        })

    # last event
    last_event_ts: Optional[str] = None
    try:
        last_ts_row = session.exec(text("SELECT MAX(ts) AS ts FROM events")).first()
        ts_val = last_ts_row["ts"] if last_ts_row else None
        if isinstance(ts_val, datetime):
            last_event_ts = ts_val.isoformat()
    except Exception:
        pass

    return {
        "database": dbname or "postgres",
        "used_bytes": used_bytes,
        "used_pretty": _pretty_bytes(used_bytes),
        "limit_bytes": DB_STORAGE_LIMIT_BYTES,
        "limit_pretty": _pretty_bytes(DB_STORAGE_LIMIT_BYTES),
        "percent_used": round((used_bytes / DB_STORAGE_LIMIT_BYTES) * 100, 2) if DB_STORAGE_LIMIT_BYTES else None,
        "tables": tables,
        "last_event_ts": last_event_ts,
        "driver": "postgresql",
    }

def _sqlite_usage(session: Session) -> Dict[str, Any]:
    # SQLite file size: PRAGMA page_count * page_size
    page_count = session.exec(text("PRAGMA page_count")).first()
    page_size = session.exec(text("PRAGMA page_size")).first()
    used_bytes = int((page_count or (0,))[0]) * int((page_size or (0,))[0])

    tables = []
    for row in session.exec(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    ):
        name = row[0]
        try:
            cnt_row = session.exec(text(f"SELECT COUNT(*) AS c FROM '{name}'")).first()
            tables.append({
                "name": name,
                "rows": int((cnt_row or {"c": 0})["c"]),
                "size_bytes": None,
                "size_pretty": None,
            })
        except Exception:
            pass

    last_event_ts: Optional[str] = None
    try:
        last_ts_row = session.exec(text("SELECT MAX(ts) AS ts FROM events")).first()
        ts_val = last_ts_row["ts"] if last_ts_row else None
        if isinstance(ts_val, datetime):
            last_event_ts = ts_val.isoformat()
    except Exception:
        pass

    return {
        "database": "sqlite",
        "used_bytes": used_bytes,
        "used_pretty": _pretty_bytes(used_bytes),
        "limit_bytes": DB_STORAGE_LIMIT_BYTES,
        "limit_pretty": _pretty_bytes(DB_STORAGE_LIMIT_BYTES),
        "percent_used": round((used_bytes / DB_STORAGE_LIMIT_BYTES) * 100, 2) if DB_STORAGE_LIMIT_BYTES else None,
        "tables": tables,
        "last_event_ts": last_event_ts,
        "driver": "sqlite",
    }

def _pretty_bytes(n: int) -> str:
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < step:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n/1.0:.1f} {unit}" if unit in ("KB", "MB") else f"{n:.0f} {unit}"
        n /= step
    return f"{n:.1f} PB"

def get_db_usage() -> Dict[str, Any]:
    with get_session() as session:
        backend = engine.url.get_backend_name()
        if backend.startswith("postgresql"):
            return _pg_usage(session)
        return _sqlite_usage(session)

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/db_usage")
def db_usage():
    """
    Return current DB size and top tables (Postgres) or file size (SQLite).
    """
    backend = engine.dialect.name  # 'postgresql' | 'sqlite' | ...
    out = {"backend": backend, "ok": True}

    try:
        if backend.startswith("postgres"):
            with engine.connect() as conn:
                # total DB size
                db_bytes = conn.execute(
                    text("SELECT pg_database_size(current_database())")
                ).scalar_one()

                # top tables by total size
                rows = conn.execute(text("""
                    SELECT
                      schemaname,
                      relname,
                      n_live_tup::bigint AS rows,
                      pg_total_relation_size(relid) AS bytes
                    FROM pg_stat_user_tables
                    ORDER BY bytes DESC
                    LIMIT 8
                """)).mappings().all()

                out["db_bytes"] = int(db_bytes)
                out["tables"] = [
                    {
                        "schema": r["schemaname"],
                        "name": r["relname"],
                        "rows": int(r["rows"]),
                        "bytes": int(r["bytes"]),
                    }
                    for r in rows
                ]

        elif backend.startswith("sqlite"):
            # sqlite file size
            path = engine.url.database or "events.db"
            size = os.path.getsize(path) if os.path.exists(path) else 0
            out["db_bytes"] = int(size)
            out["tables"] = []
        else:
            out["db_bytes"] = None
            out["tables"] = []
    except Exception as e:
        out["ok"] = False
        out["error"] = str(e)

    return out
