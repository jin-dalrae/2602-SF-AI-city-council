"""Persistence layer.

Three concerns live here:
- Findings snapshot (current state, JSON object, periodic full-overwrite).
- History (append-only JSONL with a tail-trim policy).
- Episodic memory (loaded into RAM once at startup; appends are JSONL).

All disk I/O is wrapped in `asyncio.to_thread` so the agent loop never blocks
on file handles.
"""

import asyncio
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

STORAGE_DIR = Path(__file__).resolve().parent.parent / "data"
FINDINGS_FILE = STORAGE_DIR / "findings.json"
HISTORY_FILE = STORAGE_DIR / "findings_history.jsonl"
LEGACY_HISTORY_FILE = STORAGE_DIR / "findings_history.json"
MEMORY_FILE = STORAGE_DIR / "agent_memory.jsonl"
LEGACY_MEMORY_FILE = STORAGE_DIR / "agent_memory.json"

# Tail-trim policy for the JSONL files. We sweep on startup; sync writes
# stay O(1) append.
HISTORY_MAX_ENTRIES = 5000
MEMORY_MAX_ENTRIES = 200

# In-memory caches initialised by `init_storage()` on app startup.
_memory_cache: list[dict] = []
_memory_lock = Lock()
_history_lock = Lock()


def ensure_storage() -> None:
    STORAGE_DIR.mkdir(exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Findings snapshot ─────────────────────────────────────────────────────

def _save_findings_sync(findings_store: dict) -> None:
    ensure_storage()
    to_save = {k: v for k, v in findings_store.items() if not k.startswith("_")}
    tmp = FINDINGS_FILE.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(to_save, f, indent=2, default=str)
    tmp.replace(FINDINGS_FILE)


async def save_findings(findings_store: dict) -> None:
    await asyncio.to_thread(_save_findings_sync, findings_store)


def load_findings() -> dict:
    """Sync — called once at startup before any concurrent work begins."""
    if not FINDINGS_FILE.exists():
        return {}
    try:
        with open(FINDINGS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


# ── History (append-only JSONL) ───────────────────────────────────────────

def _migrate_legacy_history() -> None:
    """One-time migration from the old JSON-array history to JSONL."""
    if not LEGACY_HISTORY_FILE.exists() or HISTORY_FILE.exists():
        return
    try:
        with open(LEGACY_HISTORY_FILE, "r") as f:
            entries = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    with open(HISTORY_FILE, "w") as out:
        for entry in entries[-HISTORY_MAX_ENTRIES:]:
            out.write(json.dumps(entry, default=str) + "\n")
    LEGACY_HISTORY_FILE.unlink(missing_ok=True)


def _trim_history_sync() -> None:
    """Rewrite the file with only the tail of entries. Called at startup."""
    if not HISTORY_FILE.exists():
        return
    with open(HISTORY_FILE, "r") as f:
        lines = f.readlines()
    if len(lines) <= HISTORY_MAX_ENTRIES:
        return
    with open(HISTORY_FILE, "w") as f:
        f.writelines(lines[-HISTORY_MAX_ENTRIES:])


def _append_history_sync(finding: dict) -> None:
    ensure_storage()
    entry = dict(finding)
    entry.setdefault("saved_at", _now_iso())
    with _history_lock:
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")


async def append_to_history(finding: dict) -> None:
    await asyncio.to_thread(_append_history_sync, finding)


def _read_history_sync(agent_name: str | None, limit: int) -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    out: list[dict] = []
    with open(HISTORY_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if agent_name and entry.get("agent_name") != agent_name:
                continue
            out.append(entry)
    return out[-limit:]


def get_history(agent_name: str | None = None, limit: int = 50) -> list[dict]:
    """Sync — used by the GET /api/findings/history route. Reads the whole
    file each call; that's fine for a single-shot HTTP read but not for a
    hot loop."""
    return _read_history_sync(agent_name, limit)


# ── Episodic memory (in-RAM + JSONL appends) ──────────────────────────────

def _migrate_legacy_memory() -> None:
    if not LEGACY_MEMORY_FILE.exists() or MEMORY_FILE.exists():
        return
    try:
        with open(LEGACY_MEMORY_FILE, "r") as f:
            entries = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    with open(MEMORY_FILE, "w") as out:
        for entry in entries[-MEMORY_MAX_ENTRIES:]:
            out.write(json.dumps(entry) + "\n")
    LEGACY_MEMORY_FILE.unlink(missing_ok=True)


def _load_memory_into_cache() -> None:
    """Called once at startup. Trims the on-disk file too if it's grown."""
    global _memory_cache
    if not MEMORY_FILE.exists():
        _memory_cache = []
        return
    entries: list[dict] = []
    with open(MEMORY_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if len(entries) > MEMORY_MAX_ENTRIES:
        entries = entries[-MEMORY_MAX_ENTRIES:]
        with open(MEMORY_FILE, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
    _memory_cache = entries


def _append_memory_sync(entry: dict) -> None:
    ensure_storage()
    with _memory_lock:
        _memory_cache.append(entry)
        if len(_memory_cache) > MEMORY_MAX_ENTRIES * 2:
            # Periodic compaction: rewrite the file with the trimmed tail.
            trimmed = _memory_cache[-MEMORY_MAX_ENTRIES:]
            with open(MEMORY_FILE, "w") as f:
                for e in trimmed:
                    f.write(json.dumps(e) + "\n")
            _memory_cache[:] = trimmed
        else:
            with open(MEMORY_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")


async def save_memory(agent_name: str, summary: str, embedding: list[float]) -> None:
    entry = {
        "agent": agent_name,
        "summary": summary,
        "embedding": embedding,
        "timestamp": _now_iso(),
    }
    await asyncio.to_thread(_append_memory_sync, entry)


def _cosine_sim(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def search_memory(
    agent_name: str,
    query_embedding: list[float],
    limit: int = 3,
    threshold: float = 0.7,
) -> list[str]:
    """Pure-RAM lookup against the cache. No disk I/O."""
    if not query_embedding:
        return []
    with _memory_lock:
        agent_mems = [m for m in _memory_cache if m.get("agent") == agent_name]
    if not agent_mems:
        return []
    scored = [
        (_cosine_sim(query_embedding, m.get("embedding") or []), m.get("summary", ""))
        for m in agent_mems
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for score, s in scored[:limit] if score > threshold]


# ── Init ──────────────────────────────────────────────────────────────────

def init_storage() -> None:
    """Run once at startup. Migrates legacy formats, trims, warms caches."""
    ensure_storage()
    _migrate_legacy_history()
    _migrate_legacy_memory()
    _trim_history_sync()
    _load_memory_into_cache()
