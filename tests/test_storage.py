"""Storage round-trip tests. Use a temporary data dir so we don't touch the
real backend/data while running."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

import backend.services.storage as storage


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(storage, "FINDINGS_FILE", tmp_path / "findings.json")
    monkeypatch.setattr(storage, "HISTORY_FILE", tmp_path / "findings_history.jsonl")
    monkeypatch.setattr(storage, "LEGACY_HISTORY_FILE", tmp_path / "findings_history.json")
    monkeypatch.setattr(storage, "MEMORY_FILE", tmp_path / "agent_memory.jsonl")
    monkeypatch.setattr(storage, "LEGACY_MEMORY_FILE", tmp_path / "agent_memory.json")
    storage._memory_cache.clear()
    yield


def test_findings_snapshot_roundtrip():
    findings = {
        "Safety Commissioner:Burglary up": {"agent_name": "Safety Commissioner", "severity": "high"},
        "_traits_Safety Commissioner": ["Expert Data Analyst"],
    }
    asyncio.run(storage.save_findings(findings))
    loaded = storage.load_findings()
    # Internal `_`-prefixed keys are filtered out on save.
    assert "Safety Commissioner:Burglary up" in loaded
    assert "_traits_Safety Commissioner" not in loaded


def test_history_jsonl_append_and_read():
    async def write_some():
        for i in range(3):
            await storage.append_to_history({"agent_name": "Test Agent", "n": i, "severity": "low"})

    asyncio.run(write_some())
    history = storage.get_history(limit=10)
    assert len(history) == 3
    assert [h["n"] for h in history] == [0, 1, 2]


def test_history_filters_by_agent():
    async def write_some():
        await storage.append_to_history({"agent_name": "A", "severity": "low"})
        await storage.append_to_history({"agent_name": "B", "severity": "low"})
        await storage.append_to_history({"agent_name": "A", "severity": "low"})

    asyncio.run(write_some())
    assert len(storage.get_history(agent_name="A")) == 2
    assert len(storage.get_history(agent_name="B")) == 1


def test_memory_load_and_search_uses_cache(monkeypatch):
    # Seed legacy JSON-array memory; init_storage should migrate it to JSONL.
    legacy = storage.LEGACY_MEMORY_FILE
    legacy.write_text(
        json.dumps(
            [
                {"agent": "Agent A", "summary": "old finding", "embedding": [1.0, 0.0]},
                {"agent": "Agent B", "summary": "unrelated", "embedding": [0.0, 1.0]},
            ]
        )
    )
    storage.init_storage()
    assert storage.MEMORY_FILE.exists()
    assert not legacy.exists()

    # Cosine similarity should rank perfectly-aligned vectors first.
    hits = storage.search_memory("Agent A", [1.0, 0.0], limit=1)
    assert hits == ["old finding"]


def test_legacy_history_migration():
    legacy = storage.LEGACY_HISTORY_FILE
    legacy.write_text(json.dumps([{"agent_name": "X", "n": 1}, {"agent_name": "Y", "n": 2}]))
    storage.init_storage()
    history = storage.get_history(limit=10)
    assert len(history) == 2
    assert not legacy.exists()
