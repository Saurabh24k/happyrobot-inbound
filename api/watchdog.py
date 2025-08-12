import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, Iterable, Set

from sqlmodel import select

from .db import get_session
from .models import Event, Offer, ToolCall, Utterance

FINAL_LABELS = {"booked", "no-agreement", "no-match", "failed-auth", "abandoned", "transfer_failed"}

WATCHDOG_ENABLED = os.getenv("WATCHDOG_ENABLED", "1") == "1"
WATCHDOG_INTERVAL_SEC = int(os.getenv("WATCHDOG_INTERVAL_SEC", "60"))
WATCHDOG_TTL_SEC = int(os.getenv("WATCHDOG_TTL_SEC", "180"))
WATCHDOG_LEADER = os.getenv("WATCHDOG_LEADER", "1") == "1"  # set to '0' on non-leader pods if you scale out

def _utcnow() -> datetime:
    return datetime.utcnow()

async def _loop(interval_sec: int, ttl_sec: int):
    """
    Mark sessions as 'abandoned' if they've shown activity (offers/toolcalls/utterances/activity events)
    but have no final event after ttl_sec.
    """
    while True:
        try:
            await asyncio.sleep(interval_sec)
            cutoff = _utcnow() - timedelta(seconds=ttl_sec)

            with get_session() as s:
                sid_set: Set[str] = set()

                # Use any footprint to discover sessions
                offer_sids = s.exec(select(Offer.session_id).where(Offer.session_id.is_not(None)).distinct()).all()
                sid_set.update([sid for (sid,) in offer_sids if sid])

                tc_sids = s.exec(select(ToolCall.session_id).where(ToolCall.session_id.is_not(None)).distinct()).all()
                sid_set.update([sid for (sid,) in tc_sids if sid])

                utt_sids = s.exec(select(Utterance.session_id).where(Utterance.session_id.is_not(None)).distinct()).all()
                sid_set.update([sid for (sid,) in utt_sids if sid])

                evt_sids = s.exec(select(Event.session_id).where(Event.session_id.is_not(None)).distinct()).all()
                sid_set.update([sid for (sid,) in evt_sids if sid])

                if not sid_set:
                    continue

                for sid in sid_set:
                    # Skip finalized sessions
                    final = s.exec(select(Event).where(Event.session_id == sid, Event.event.in_(FINAL_LABELS))).first()
                    if final:
                        continue

                    # Find last activity timestamp:
                    # - Prefer latest Offer.t
                    # - Else latest Event.ts (including 'activity' events)
                    last_offer = s.exec(
                        select(Offer).where(Offer.session_id == sid).order_by(Offer.t.desc()).limit(1)
                    ).first()
                    last_event = s.exec(
                        select(Event).where(Event.session_id == sid).order_by(Event.ts.desc()).limit(1)
                    ).first()

                    last_ts: Optional[datetime] = None
                    if last_offer and last_offer.t:
                        last_ts = last_offer.t
                    if last_event and last_event.ts and (last_ts is None or last_event.ts > last_ts):
                        last_ts = last_event.ts

                    if not last_ts:
                        continue

                    if last_ts <= cutoff:
                        s.add(Event(event="abandoned", session_id=sid, extra={"source": "watchdog"}))

                s.commit()

        except asyncio.CancelledError:
            break
        except Exception:
            # Never kill the app on watchdog errors
            continue

def start_watchdog(app) -> Optional[asyncio.Task]:
    """
    Call from FastAPI startup. Returns the task handle (or None if disabled/not leader).
    """
    if not WATCHDOG_ENABLED or not WATCHDOG_LEADER:
        return None
    task = asyncio.create_task(_loop(WATCHDOG_INTERVAL_SEC, WATCHDOG_TTL_SEC))
    return task

async def stop_watchdog(task: Optional[asyncio.Task]) -> None:
    """
    Call from FastAPI shutdown with the task returned by start_watchdog().
    """
    if not task:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
