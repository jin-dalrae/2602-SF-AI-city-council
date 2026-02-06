"""
Persistence layer for agent findings.
Saves findings to a JSON file so they survive server restarts.
"""

import json
import os
from datetime import datetime
from pathlib import Path

STORAGE_DIR = Path(__file__).resolve().parent.parent / "data"
FINDINGS_FILE = STORAGE_DIR / "findings.json"
HISTORY_FILE = STORAGE_DIR / "findings_history.json"


def ensure_storage():
    """Create storage directory if it doesn't exist."""
    STORAGE_DIR.mkdir(exist_ok=True)


def save_findings(findings_store: dict) -> None:
    """Save current findings to disk."""
    ensure_storage()
    # Filter out internal keys (starting with _)
    to_save = {k: v for k, v in findings_store.items() if not k.startswith("_")}
    with open(FINDINGS_FILE, "w") as f:
        json.dump(to_save, f, indent=2, default=str)


def load_findings() -> dict:
    """Load findings from disk if they exist."""
    if not FINDINGS_FILE.exists():
        return {}
    try:
        with open(FINDINGS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def append_to_history(finding: dict) -> None:
    """Append a finding to the history file for long-term storage."""
    ensure_storage()
    history = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []
    
    # Add timestamp if not present
    finding_copy = finding.copy()
    if "saved_at" not in finding_copy:
        finding_copy["saved_at"] = datetime.now().isoformat()
    
    history.append(finding_copy)
    
    # Keep only last 500 entries to prevent unbounded growth
    history = history[-500:]
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, default=str)


def get_history(agent_name: str = None, limit: int = 50) -> list:
    """Get historical findings, optionally filtered by agent name."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []
    
    if agent_name:
        history = [h for h in history if h.get("agent_name") == agent_name]
    
    return history[-limit:]
