# AI City Council

![AI City Council Hero](docs/hero.png)

> A multi-agent civic intelligence platform for San Francisco. Nine AI agents
> continuously read SF Open Data, news, and community signals, surface the
> civic issues that need attention, and turn each one into a data-cited email
> to the official who can act on it.

`/` is a public status-page landing. `/dashboard` is the live operations
console. The agents run 24/7 on a 60-second loop.

---

## Why

San Francisco publishes 500+ public datasets. Almost none of them get read in
time to matter — the data is buried in Socrata APIs, the news is scattered,
and the people who could act on a pattern rarely see it before it becomes a
crisis. AICC reads it all continuously, finds the story, and tells you what to
do next.

---

## What it does

**Nine specialized agents**, each owning a slice of city operations:

| Agent | Domain | Source |
|---|---|---|
| Safety Commissioner | Crime trends, district hot-spots | SFPD incidents |
| Transit Authority | Enforcement trajectory, equity | SFMTA citations |
| Infrastructure Foreman | Pothole / graffiti backlogs | 311 service requests |
| City Comptroller | Spending, reallocation candidates | City budget |
| Planning Commissioner | Approval bottlenecks, housing pipeline | Building permits |
| Civic Correspondent | Real-time news context for all agents | You.com |
| Community Watch | Ground-truth resident reports | r/sanfrancisco |
| SF Tech Scouter | Ecosystem sentiment, displacement | X / Twitter |
| Policy Coordinator | Merges signals into city-wide briefings | (meta-agent) |

Each cycle runs `fetch → analyze → act → evolve → memorize → broadcast`:

- **Analyze** — Gemini interprets each agent's snapshot against episodic
  memory, writes a severity-graded finding, and a coordinator merges related
  signals across departments.
- **Act** — `high`/`critical` findings auto-open GitHub issues (Composio, with
  a per-issue cooldown). Any finding can be turned into a data-cited email to
  the relevant SF official and sent via Gmail.
- **Memorize** — finding summaries + embeddings are stored so future cycles
  are contextualized against past patterns.

All heavy I/O is wrapped in `asyncio.to_thread`, so the FastAPI event loop
never blocks on a model call or a disk write.

---

## The two surfaces

**Landing (`/`)** — an editorial status page. Fraunces serif display type, an
animated ECG "heartbeat", a manifesto, and the current top finding rendered as
a featured article card. Read-only; safe to expose publicly.

**Dashboard (`/dashboard`)** — an operations console in a Bloomberg-terminal
register: white-on-near-black, JetBrains Mono for data, full-saturation
severity colors as the primary signal. Findings are a severity-sorted table;
clicking a row opens a slide-in detail panel. A live brain-feed streams agent
reasoning. Fully keyboard-driven:

| Key | Action |
|---|---|
| `j` / `k` | Navigate findings |
| `Enter` / `o` | Open selected |
| `e` | Draft email for selected |
| `Esc` | Close panel / modal |
| `s` / `Shift+S` | Start / stop agents |
| `r` | Reload history |
| `t` | Set API token |
| `?` | Shortcut help |

---

## Routes

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | — | Landing |
| GET | `/dashboard` | — | Operations console |
| GET | `/terms`, `/privacy` | — | Legal (CA / CCPA) |
| GET | `/api/agents/status` | — | Agent roster + counts |
| GET | `/api/findings` | — | SSE live stream |
| GET | `/api/findings/history` | — | Historical findings |
| POST | `/api/agents/start` · `/stop` | token | Lifecycle control |
| POST | `/api/email/draft` · `/send` | token | Email drafting / sending |

Mutating routes require a bearer token (`API_AUTH_TOKEN`). If the token is
unset on the server, those routes return `503` by design — auth fails loud
rather than silently disabling.

---

## Architecture

```
backend/
├── main.py              # FastAPI app, lifespan, page routes
├── config.py            # env-driven config (models, intervals, severity vocab)
├── deps.py              # singleton clients (Socrata, Composio)
├── auth.py              # bearer-token dependency for mutating routes
├── state.py             # shared in-process state (findings, queues, tasks)
├── api/
│   ├── agents.py        # /api/agents/* + the agent launcher
│   ├── findings.py      # /api/findings (SSE) + history
│   └── email.py         # /api/email/{draft,send}
├── events/
│   └── broadcaster.py   # SSE fan-out from a shared event queue
├── agents/
│   ├── base.py          # CityAgent: run_loop, analyze, memory, collaboration
│   ├── socrata_agent.py # config-driven Socrata agent factory
│   ├── definitions.py   # SFPD/SFMTA/PublicWorks/Budget/Planning specs
│   ├── reddit.py · x_agent.py · sf_news.py · coordinator.py
├── services/
│   ├── llm.py           # Gemini wrapper (analysis, embeddings, evolve)
│   ├── socrata.py       # SF Open Data client
│   ├── you_api.py       # You.com search
│   ├── composio_tools.py# civic action triggers (GitHub issues)
│   ├── email_drafting.py# email draft + send
│   └── storage.py       # JSONL history + RAM-cached vector memory
└── data/                # runtime persistence (gitignored)

static/
├── landing.html         # / — editorial status page
├── index.html           # /dashboard — operations console
├── app.js               # dashboard SSE + render + keyboard
├── terms.html · privacy.html · _legal.css
docs/                    # PRD, implementation notes, hero image
scripts/                 # smoke tests for You.com + Composio
tests/                   # pytest (storage round-trip + severity contract)
```

---

## Quickstart

```bash
pip install -r requirements.txt

cat > .env <<'EOF'
GEMINI_API_KEY=your_key            # required
YOU_COM_API_KEY=your_key           # required for news + verification
COMPOSIO_API_KEY=your_key          # optional: Reddit, X, GitHub, Gmail
API_AUTH_TOKEN=$(openssl rand -hex 24)   # required for mutating routes
EOF

python -m uvicorn backend.main:app --reload
```

- Visit `http://localhost:8000/` for the landing, `…/dashboard` for the console.
- On the dashboard, press `t` (or click 🔑) and paste your `API_AUTH_TOKEN` so
  Start/Stop and email actions authenticate.

### Optional configuration

| Var | Default | Effect |
|---|---|---|
| `GEMINI_MODEL` | `gemini-2.0-flash` | LLM used for analysis |
| `AGENT_LOOP_INTERVAL` | `60` | Seconds between agent cycles |
| `NEWS_LOOP_INTERVAL` | `90` | Seconds between news cycles |
| `CIVIC_ACTION_COOLDOWN_SECONDS` | `3600` | Min gap between duplicate GitHub issues |

### Tests

```bash
pytest tests/
```

---

## Operational notes

- Persistence lives in `backend/data/`: `findings.json` is the current
  snapshot; `findings_history.jsonl` is append-only; `agent_memory.jsonl`
  holds summaries + embeddings, loaded into RAM at startup. Legacy
  JSON-array files auto-migrate on first boot.
- The Policy Coordinator runs as a regular agent — it reads sibling findings
  rather than fetching its own data.
- Severity vocabulary is canonical (`low` / `medium` / `high` / `critical`)
  and enforced from `config.py`.

---

## Tech stack

- **Intelligence** — Gemini 2.0 Flash (analysis + embeddings)
- **Action** — Composio (GitHub issues, Gmail)
- **Context** — You.com Search API
- **Backend** — Python 3.11, FastAPI, SSE
- **Frontend** — zero-build vanilla JS; dashboard themed with CSS variables
  (Tailwind CDN for layout utilities), landing in hand-written CSS with
  Fraunces / Inter / JetBrains Mono

---

## Legal

[Terms of Service](/terms) · [Privacy Policy](/privacy) — written for
California (CCPA / CPRA / Shine the Light), governing law California.

---

*Built for San Francisco residents. Open data, open advocacy.*
