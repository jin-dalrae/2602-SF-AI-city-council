# AI City Council

![AI City Council Hero](docs/hero.png)

A multi-agent civic intelligence platform for San Francisco. Specialized AI agents continuously monitor SF Open Data, news, and community signals; surface high-impact issues; and help residents take action through evidence-backed emails to city officials.

---

## What it does

- **9 specialized agents** run on a loop, each owning a slice of city operations:
  - Safety Commissioner (SFPD incidents)
  - Transit Authority (SFMTA citations)
  - Infrastructure Foreman (311 / Public Works)
  - City Comptroller (budget)
  - Planning Commissioner (permits)
  - Civic Correspondent (real-time news via You.com)
  - Reddit Community Watch (`r/sanfrancisco`)
  - SF Tech Scouter (X/Twitter signals)
  - Policy Coordinator (meta-agent — merges related findings into systemic briefings)

- **Live SSE dashboard** at `/` shows findings as they land, with severity grading, evidence, and a brain-feed of agent reasoning.

- **Civic action loop**:
  - High/critical severity findings can auto-open GitHub issues for tracking (via Composio, with per-issue cooldown).
  - One-click email drafts to the relevant SF official, citing the data, ready to send through Composio Gmail.

---

## Architecture

```
backend/
├── main.py              # FastAPI app + lifespan
├── config.py            # env-driven config (models, intervals, severity vocab)
├── deps.py              # singleton clients (Socrata, Composio)
├── auth.py              # bearer-token dependency for mutating routes
├── state.py             # shared in-process state (findings, queues, tasks)
├── api/
│   ├── agents.py        # /api/agents/* (start, stop, status)
│   ├── findings.py      # /api/findings (SSE) + /api/findings/history
│   └── email.py         # /api/email/{draft,send}
├── events/
│   └── broadcaster.py   # SSE fan-out from a shared event queue
├── agents/
│   ├── base.py          # CityAgent: run_loop, analyze, memory, collaboration
│   ├── socrata_agent.py # config-driven Socrata agent factory
│   ├── definitions.py   # SFPD/SFMTA/PublicWorks/Budget/Planning specs
│   ├── reddit.py
│   ├── x_agent.py
│   ├── sf_news.py
│   └── coordinator.py
├── services/
│   ├── llm.py           # Gemini wrapper (analysis, embeddings, evolve)
│   ├── socrata.py       # SF Open Data client
│   ├── you_api.py       # You.com search
│   ├── composio_tools.py# civic action triggers (GitHub issues)
│   ├── email_drafting.py# email draft + send
│   └── storage.py       # JSONL history + RAM-cached vector memory
└── data/                # runtime persistence (gitignored)

static/                  # vanilla JS dashboard (SSE)
docs/                    # PRD, implementation notes, hero image
scripts/                 # smoke tests for You.com + Composio
tests/                   # pytest suite (storage + severity contract)
```

The agent loop is `fetch → analyze → action → evolve → memorize → broadcast`, with all heavy I/O wrapped in `asyncio.to_thread` so the FastAPI event loop never blocks.

---

## Setup

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Create `.env` (gitignored):

```env
GEMINI_API_KEY=your_key            # required
YOU_COM_API_KEY=your_key           # required for news + verification
COMPOSIO_API_KEY=your_key          # optional (enables Reddit, X, GitHub, Gmail)
API_AUTH_TOKEN=pick_a_long_random_string   # required to call mutating routes

# Optional
GEMINI_MODEL=gemini-2.0-flash
AGENT_LOOP_INTERVAL=60
NEWS_LOOP_INTERVAL=90
CIVIC_ACTION_COOLDOWN_SECONDS=3600
```

`API_AUTH_TOKEN` protects `/api/agents/{start,stop}` and `/api/email/{draft,send}`. The read-only SSE stream and history endpoints stay public.

### 3. Run

```bash
python -m uvicorn backend.main:app --reload
```

Open `http://localhost:8000`. Click the 🔑 in the header and paste your `API_AUTH_TOKEN` so the dashboard can authenticate mutating actions.

### 4. Tests

```bash
pytest tests/
```

---

## Tech stack

- **Core intelligence**: Gemini 2.0 Flash
- **Action layer**: Composio (GitHub, Gmail)
- **Contextual awareness**: You.com Search API
- **Foundation**: Python (FastAPI), vanilla JS + Tailwind, SSE

---

## Operational notes

- All findings are persisted in `backend/data/`. `findings.json` is the current snapshot; `findings_history.jsonl` is append-only. Memory embeddings live in `agent_memory.jsonl` and are loaded into RAM at startup.
- High/critical findings trigger GitHub issues with a 1-hour cooldown per `(agent, issue_title)` to avoid duplicates.
- The Policy Coordinator runs as a regular agent in the loop — it reads sibling findings rather than fetching its own data.

---

## Legal

[Terms of Service](static/terms.html) · [Privacy Policy](static/privacy.html)

---

*Built for San Francisco residents. Open data, open advocacy.*
