# AI City Council — Audit Report

**Scope:** Full pass (quality + security + performance), deep restructure permitted.
**Mode:** Findings only — no code changes yet.
**Date:** 2026-05-14

---

## TL;DR

The project works as a hackathon demo but is **not safe to leave running on a public URL**. Four issues are urgent:

1. **Leaked API keys in git history** (still valid).
2. **LLM-driven self-modifying source code** — an unsandboxed `exec`-equivalent on every cycle.
3. **No auth on POST endpoints** — anyone can send emails through your Gmail account.
4. **Blocking sync I/O on async hot paths** — the event loop stalls every cycle, hiding real bugs behind sluggishness.

Beyond those, ~30 medium/quality findings — large amounts of duplication across the agent subclasses, three different `severity` vocabularies, a memory store that re-reads the whole file every cycle, etc.

I'd recommend fixing the Critical block before any restructure, then doing the deep restructure as a single follow-up PR.

---

## CRITICAL (fix before next deploy)

### C1. Live API keys leaked in git history
- Commit `a831ac1` added `.env` to the repo; commit `4c0de5d` deleted it. **The keys remain in history.**
- Leaked (still potentially valid):
  - `YOU_COM_API_KEY=ydc-sk-777d4b81fa245e85-CanTLMl5QnldMFFyfOqROWY7TnbZ`
  - `GEMINI_API_KEY=AIzaSyDEdUPdBis3BObdofkq5YVSDok9kVVXXtA`
  - `nvidia_api_key=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`
- The current `.env` (uncommitted) also has live keys for You.com, Gemini, and Composio.
- **Action:** Rotate **all four** keys immediately (You.com, Gemini, NVIDIA, Composio). Then either `git filter-repo` history or, if the repo is private and low-risk, accept the leak and rotate. NVIDIA isn't even used in the current code — verify, then drop the key entirely.

### C2. Self-modifying source code from LLM output (`storage.apply_code_update`)
- `backend/services/storage.py:147` writes arbitrary text into agent `.py` files based on a `code_update` field returned by `evolve_brain` (`backend/services/llm.py:107`), called every cycle from `base.py:163`.
- This is, effectively, **`exec()` on untrusted LLM output**, persisted to disk. One bad LLM response can break a class permanently, or inject malicious imports that get re-imported on next restart.
- Also brittle on multiple axes:
  - Indentation is inferred by string-matching the line *after* `def …`.
  - Newlines and quotes inside `new_code` get mangled by JSON encoding.
  - No syntax validation (`ast.parse`) before writing.
  - No backup or rollback.
- **Action:** Remove entirely, or gate behind an explicit feature flag (default off) that writes to a separate `evolutions/` directory for human review, never to live source.

### C3. Unauthenticated mutating endpoints
- `POST /api/agents/start`, `POST /api/agents/stop`, `POST /api/email/draft`, `POST /api/email/send` accept any request with no auth, no CSRF, no origin check.
- `/api/email/send` invokes `composio.tools.execute(slug="GMAIL_SEND_EMAIL", ...)` with an arbitrary recipient/subject/body from the request body. Anyone on the internet can spam through your Gmail.
- No CORS configuration at all — works only because the frontend is served same-origin, but there's no defense if exposed.
- **Action:** Either (a) require an auth token / signed cookie, or (b) restrict to localhost / Cloud Run IAM. At minimum, allowlist `recipient_email` to known officials.

### C4. Sync I/O on async event loop
Every cycle, the event loop blocks on disk:
- `llm.analyze_data` calls **sync** `client.models.generate_content` (`llm.py:76`) — but `evolve_brain` correctly uses `asyncio.to_thread` (`llm.py:131`). Inconsistent and the bigger one is the wrong one.
- `email_agent.draft_email` also calls **sync** `client.models.generate_content` (`email_agent.py:64`).
- `storage.save_findings`, `append_to_history`, `save_memory`, `search_memory`, `load_findings`, `apply_code_update` all use blocking `open()` from async callsites.
- Worst hotspot: `append_to_history` reads and rewrites the entire `findings_history.json` (up to 5000 entries) **for every finding emitted by every agent**. With 9 agents at ~60s, that's ~9 full rewrites/minute, all blocking.
- **Action:** Wrap LLM calls in `asyncio.to_thread`; use `aiofiles` or SQLite for storage. The history file should be append-only (JSONL) or a SQLite table.

---

## HIGH (correctness / reliability / cost)

### H1. `genai.Client(...)` instantiated at module import
- `llm.py:10` and `email_agent.py:63` build a `genai.Client` at import time. Missing `GEMINI_API_KEY` crashes the entire app rather than failing gracefully on first use.
- `email_agent.py` even re-imports `genai` and re-builds a client *inside* `draft_email`. The module-level one is unused there.
- **Action:** Single lazy module-level client in `services/llm.py`, used everywhere.

### H2. Severity vocabulary mismatch (three different schemas)
- `llm.py` SYSTEM_PROMPT requires: `"low" | "medium" | "high" | "critical"`.
- `sf_news.py` prompt instructs LLM to use: `"urgent", "moderate", "low"`.
- `actions.py` trigger condition uses: `["high", "critical", "urgent"]`.
- Net effect: SF News findings (`urgent`) trigger GitHub issues but get rendered with no severity color on the frontend (frontend likely has `severity-urgent` undefined). Other agents emit `high`/`critical` which trigger issues. `medium` is dead in `actions.py`.
- **Action:** Pick one vocabulary (`low/medium/high/critical`) and enforce in all prompts.

### H3. `actions.trigger_civic_action` will spam GitHub
- Fires whenever any agent emits `high|critical|urgent` severity. 9 agents × every 60s × no dedup = potentially dozens of duplicate GitHub issues per hour during a sustained "high" state.
- **Action:** Dedup by `issue_title` (or hash of finding key fields), respect Composio rate limits, add a cooldown window per agent.

### H4. `__pycache__` checked into git
- 15 `.pyc` files committed under `backend/`. `.gitignore` lists `__pycache__/` but pre-existing tracked files aren't ignored.
- **Action:** `git rm -r --cached backend/**/__pycache__` and commit.

### H5. SSE: duplicate findings on reconnect + no backpressure
- `findings_store` is written twice per cycle: once under `{agent}:{title}` and once under `{agent}` (`base.py:213-216`). On SSE reconnect the initial replay sends both, frontend gets a duplicate card.
- `event_queue` is unbounded — if a subscriber stalls, the `_listen_and_broadcast` keeps pumping into per-subscriber queues without limit. Memory creeps over long runs.
- **Action:** Single source-of-truth key per finding (`{agent}:{title}` only); cap queue depth; drop oldest on overflow.

### H6. Memory search is O(N) cosine in Python, blocking
- `storage.search_memory` reads the whole `agent_memory.json` (up to 200 entries), iterates with pure-Python cosine on every agent cycle. Per the architecture this fires ~9× per minute.
- **Action:** SQLite with a sqlite-vec extension, or `numpy` array + faiss-cpu, or just keep but `to_thread` it.

### H7. `socrata.needs_update` result is ignored
- `socrata.py:42-47` calls `needs_update()` and the function explicitly comments out using the result. Pure overhead — an extra HTTP round-trip every fetch with no effect.
- **Action:** Either honor the result (skip fetch if not updated, return cached) or remove the call.

### H8. `SocrataClient()` per agent, never closed
- Each `CityAgent.__init__` builds a new `httpx.AsyncClient`. Eight agents = eight client pools. None call `close()` on shutdown.
- **Action:** Single shared `SocrataClient` in app lifespan, closed on shutdown.

### H9. Bare `except Exception` everywhere swallows real bugs
- `llm.analyze_data` line 93 catches `(json.JSONDecodeError, Exception)` (the second one subsumes the first), returns a synthesized "API key needs replacement" finding by string-matching `"leaked"`/`"403"` in the error.
- `socrata.needs_update` swallows all errors, defaults to "update needed" — fine but logs to `print`.
- `reddit.py` and `x_agent.py` slug-fishing loops use `except:` (bare).
- **Action:** Narrow exceptions; log with `logger.exception(...)`; let unexpected errors propagate.

### H10. Naive `datetime.now()` in `storage.py`
- `save_memory`, `append_to_history` use `datetime.now().isoformat()` (no tz). Everything else uses UTC-aware timestamps. Sorting/filtering will silently drift by your local offset.
- **Action:** `datetime.now(timezone.utc).isoformat()` consistently.

### H11. `SFNewsAgent` doesn't inherit from `CityAgent`
- `sf_news.py:14` is a sibling class duplicating `__init__`, `run_once`, `run_loop`, and the error-output dict. Diverges from `CityAgent` — no memory, no traits, no collaboration check, no Composio actions.
- Type collision: `CityAgent.fetch_news() -> list[str]`, but `SFNewsAgent.fetch_news() -> list[dict]`. Same method name, incompatible signatures.
- **Action:** Make `SFNewsAgent` inherit from `CityAgent`, or extract a smaller `BaseAgent` interface both share.

---

## MEDIUM (quality / structure)

### M1. Five agent subclasses are 90% identical boilerplate
- `sfpd.py`, `sfmta.py`, `public_works.py`, `budget.py`, `planning.py` all follow the same pattern: `fetch_trends` + `fetch_recent` + format strings + prompt. Could be a single `SocrataAgent` parameterized by a config dict.
- **Action:** Replace with a config-driven `SocrataAgent(name, datasets, query_specs, prompt_template)`. Cuts ~300 LOC.

### M2. Class-level mutable defaults in `CityAgent`
- `datasets: dict[str, str] = {}` and `officials: list[dict] = []` (`base.py:14-15`) are *class* attributes. Safe today because every subclass overrides them, but the pattern is a footgun — anyone who does `self.officials.append(...)` mutates the class-level list shared across instances.
- **Action:** Move to instance fields or use `field(default_factory=...)`.

### M3. Three different ways to log
- `print(...)` in services (`socrata.py`, `you_api.py`, `actions.py`, `sf_news.py`).
- `logger.info/error` in `main.py`.
- `self._log_brain(...)` for agent feed events.
- **Action:** One `logging.getLogger` per module; brain feed remains separate (it's a domain event, not a log).

### M4. `findings_store` is too generic
- Used for: actual findings, `_traits_<agent>` persistence, `_news_headlines` shared cache, internal scratch. The `_`-prefix convention is ad-hoc and breaks if any key happens to start with underscore.
- **Action:** Split into `findings`, `agent_state` (traits), and `shared_context` (news headlines). Three dicts, clear ownership.

### M5. `check_collaborations` re-defines `STOP_WORDS` every call
- 140+ word stop-list constructed on every agent cycle. Trivial cost but unnecessary.
- **Action:** Module-level constant.

### M6. `check_collaborations` is O(N²) keyword overlap
- For each finding, scans every other finding's text. With 9 agents and emerging issues, that's bounded but the cost rises with the number of issues kept in `findings_store`. Also, two-word overlap is a very weak signal — easily fires on coincidental shared filler words.
- **Action:** Use embedding similarity (you already have `get_embedding`) with a similarity threshold ≥ 0.75, or TF-IDF + cosine. Or run collaboration only via the `PolicyCoordinator` rather than from each agent's loop.

### M7. LLM JSON parsing is fragile
- `analyze_data` manually strips ` ```json ` fences. Should use `response_mime_type="application/json"` like `evolve_brain` does — Gemini will guarantee valid JSON. Saves a parse failure mode.
- **Action:** Set `response_mime_type` on every JSON-shaped call.

### M8. Email draft `to` addresses can be empty
- `email_agent.draft_email` builds `to_addresses` from `officials`. `SFNewsAgent` has officials defined but Reddit / X / Planning have only one each. If the LLM's `to` field is also empty, the draft has no recipient. Currently silently accepted.
- **Action:** Validate non-empty `to` before returning the draft.

### M9. Frontend (`static/app.js`) is a 956-line single file
- Everything in one module, all globals, no build step. Hard to reason about state, SSE handling, and the modal flow together.
- **Action:** Optional — for a hackathon dashboard this is fine. If deep-restructuring, split into `sse.js`, `cards.js`, `email.js`, `state.js`.

### M10. Hardcoded `gemini-2.0-flash` in two places
- `llm.py:11`, `email_agent.py:65`. Should come from env var so model upgrades don't require code changes.
- **Action:** `MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")`.

### M11. `_launch_agent` stagger uses `(i+1) * 5` seconds
- Agent 8 waits 40s before its first run. Fine as a thundering-herd mitigation, but inelegant — `asyncio.gather` with a `Semaphore` or `asyncio.as_completed` over actual fetch tasks is more principled.
- **Action:** Low priority — leave or replace with a semaphore.

### M12. `Cloud Run` Dockerfile pulls full requirements without pinning
- `requirements.txt` has no versions. A `composio` major version bump can break the slug-fishing.
- **Action:** Pin (or at least `>=X,<Y`) on `composio`, `composio-langchain`, `google-genai`.

---

## LOW (cleanup)

- **L1.** `you_agent.py` at project root — manual test, unrelated to runtime. Move to `scripts/` or delete.
- **L2.** `test_composio_manual.py` at project root — same. Move or delete.
- **L3.** `old/` directory — `market_sim.py`, `seller_agent.py` look unrelated to this project. Delete or move out of the repo.
- **L4.** Empty `data/` directory at project root (real data lives in `backend/data/`). Delete.
- **L5.** `__pycache__/` directories on disk (already covered above — H4 is the git side).
- **L6.** `ai_city_council_hero_vision_1770422532607.png` (60KB) at project root — move to `docs/` or `static/`.
- **L7.** `implementation.md` (19KB) and `PRD.md` (13KB) at project root — fine, but consider `docs/`.
- **L8.** `agent_status` dict in `main.py` accumulates forever — old entries from stopped agents are never cleaned up. Tiny memory leak.
- **L9.** `findings.get('issue_title')[:50]` in `base.py:149` — crashes if title is `None`. Use `(... or '')[:50]`.
- **L10.** `update_agent_status` in `main.py` is mostly write-only after startup — agent loop's own success/error states never re-call it. Either wire it in or remove.
- **L11.** README claims (`Self-Directed Code Evolution`, `vector store`) are aspirational vs. what's implemented (a JSON file with brute-force cosine; LLM-driven file rewrites). Either dial back the marketing or treat C2 as the bar.

---

## Architecture proposal (deep restructure)

Current layout mixes services, agents, and a stray top-level email agent. Suggested:

```
.
├── pyproject.toml              # replace bare requirements.txt; pin versions
├── README.md
├── docs/
│   ├── PRD.md
│   ├── implementation.md
│   ├── ARCHITECTURE.md          # new — explain agent loop, SSE, storage
│   └── hero.png
├── scripts/
│   ├── you_api_smoke.py         # was you_agent.py
│   └── composio_smoke.py        # was test_composio_manual.py
├── backend/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, routes, lifespan
│   ├── config.py                # NEW: env loading, model names, feature flags
│   ├── deps.py                  # NEW: singleton clients (genai, socrata, composio)
│   ├── api/                     # NEW: route modules
│   │   ├── agents.py            # /api/agents/*
│   │   ├── findings.py          # /api/findings, /api/findings/history
│   │   └── email.py             # /api/email/*
│   ├── events/                  # NEW: SSE broadcaster + event queue
│   │   └── broadcaster.py
│   ├── agents/
│   │   ├── base.py              # CityAgent abstract
│   │   ├── socrata_agent.py     # NEW: config-driven base for SFPD/SFMTA/etc.
│   │   ├── definitions.py       # NEW: dict of {name: SocrataAgentConfig}
│   │   ├── reddit.py            # keeps custom fetch
│   │   ├── x.py                 # keeps custom fetch
│   │   ├── sf_news.py           # inherits from CityAgent now
│   │   └── coordinator.py
│   ├── services/
│   │   ├── llm.py               # async-first, lazy client
│   │   ├── socrata.py           # shared client
│   │   ├── you_api.py
│   │   ├── composio_tools.py    # was actions.py + send_email
│   │   └── email_drafting.py    # was email_agent.py
│   ├── storage/                 # NEW: split storage concerns
│   │   ├── findings.py          # current state (in-memory + JSON snapshot)
│   │   ├── history.py           # JSONL append-only or SQLite
│   │   └── memory.py            # vector memory (SQLite + numpy)
│   └── data/                    # runtime state (gitignored)
├── static/
│   ├── index.html
│   ├── favicon.ico
│   └── js/
│       ├── app.js               # entry
│       ├── sse.js
│       ├── cards.js
│       └── email.js
└── tests/                       # NEW
    ├── test_socrata_agent.py
    ├── test_storage_history.py
    └── test_severity_schema.py
```

Key design moves:
- **One `SocrataAgent` config-driven class** replaces five near-identical subclasses.
- **`backend/deps.py`** owns singleton clients (genai, httpx, composio) injected into agents — fixes H1, H8.
- **`storage/` split** lets `history` move to JSONL/SQLite without touching `findings` (fixes C4 hotspot).
- **`config.py`** centralizes severity vocabulary, model names, feature flags (including `ENABLE_CODE_EVOLUTION=false`).
- **`events/broadcaster.py`** extracted from `main.py` so the SSE wiring is testable.
- **`api/` split** keeps `main.py` small and lets each route module own its request/response models.

---

## Suggested fix order

A. **Critical safety (single PR, ~half day)**
   1. Rotate keys (you, Gemini, Composio, NVIDIA if used).
   2. Remove `apply_code_update` + `code_update` branch in `evolve_brain` (C2).
   3. Add a simple auth token check on `/api/agents/*` and `/api/email/*` (C3).
   4. Wrap remaining sync LLM calls in `asyncio.to_thread` (C4 — narrow scope).
   5. `git rm -r --cached backend/**/__pycache__` (H4).

B. **High-severity correctness (next PR, ~1 day)**
   6. Unify severity vocabulary (H2).
   7. Dedup `actions.trigger_civic_action` and add cooldown (H3).
   8. Fix double-keying in `findings_store` (H5).
   9. Switch storage to JSONL/SQLite for `history` + `memory` (C4, H6).
   10. Single `SocrataClient` in app lifespan (H8).
   11. Make `SFNewsAgent` inherit from `CityAgent` (H11).

C. **Deep restructure (separate PR, ~1–2 days)**
   12. Apply the directory layout above; collapse the five Socrata agents into one config-driven class (M1).
   13. Add tests for the storage layer and the severity-schema contract.
   14. Frontend split (optional — M9).

Items in section A are independent of restructure and worth shipping first.

---

## What I want from you next

Tell me which of these to act on. Three reasonable cuts:

- **"Just the Critical block"** — I do A, you re-review, restructure later.
- **"Critical + High"** — I do A and B in two PRs.
- **"Full plan, all three sections"** — I do A→B→C sequentially.

Or call out anything you disagree with or want descoped (e.g. "keep `apply_code_update` but gated by a flag" or "skip the frontend split").
