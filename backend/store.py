"""Simple session store: in-memory cache with JSON files on disk for persistence."""
import json
import re
from pathlib import Path
from typing import Dict, Optional

from .models import Session

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sessions"
DATA_DIR.mkdir(parents=True, exist_ok=True)
_cache: Dict[str, Session] = {}


def _safe(session_id: str) -> str:
    if not re.fullmatch(r"[a-f0-9-]{36}", session_id):
        raise KeyError(session_id)
    return session_id


def save(session: Session) -> None:
    _cache[session.id] = session
    (DATA_DIR / f"{_safe(session.id)}.json").write_text(session.model_dump_json(indent=2))


def get(session_id: str) -> Optional[Session]:
    sid = _safe(session_id)
    if sid in _cache:
        return _cache[sid]
    path = DATA_DIR / f"{sid}.json"
    if path.exists():
        s = Session(**json.loads(path.read_text()))
        _cache[sid] = s
        return s
    return None
