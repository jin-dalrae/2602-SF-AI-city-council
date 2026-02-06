
╭───────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                         │
│                                                                                           │
│ AI City Council - Implementation Plan                                                     │
│                                                                                           │
│ Context                                                                                   │
│                                                                                           │
│ Build a real-time multi-agent civic dashboard for SF NGOs. 5 AI agents continuously       │
│ monitor SF Open Data (data.sfgov.org), use Gemini to analyze issues and generate policy   │
│ recommendations, and display findings on a live dashboard. Composio handles email         │
│ drafting to city officials.                                                               │
│                                                                                           │
│ Architecture                                                                              │
│                                                                                           │
│ project/                                                                                  │
│ ├── backend/                                                                              │
│ │   ├── main.py                 # FastAPI server + SSE + static serving                   │
│ │   ├── agents/                                                                           │
│ │   │   ├── __init__.py                                                                   │
│ │   │   ├── base.py             # Base CityAgent class                                    │
│ │   │   ├── sfpd.py             # Crime incident analysis                                 │
│ │   │   ├── sfmta.py            # Transit performance                                     │
│ │   │   ├── public_works.py     # 311 service requests                                    │
│ │   │   ├── budget.py           # City budget/expenditures                                │
│ │   │   └── planning.py         # Building permits                                        │
│ │   ├── services/                                                                         │
│ │   │   ├── __init__.py                                                                   │
│ │   │   ├── socrata.py          # Socrata API client                                      │
│ │   │   ├── llm.py              # Gemini wrapper                                          │
│ │   │   └── you_api.py          # You.com API for context                                 │
│ │   └── email_agent.py          # Composio email drafting                                 │
│ ├── static/                                                                               │
│ │   ├── index.html              # Dashboard UI                                            │
│ │   └── app.js                  # SSE client + rendering                                  │
│ ├── requirements.txt                                                                      │
│ └── .env                                                                                  │
│                                                                                           │
│ Datasets (Socrata IDs)                                                                    │
│ Agent: SFPD                                                                               │
│ Dataset: Police Incident Reports 2018+                                                    │
│ ID: wg3w-h783                                                                             │
│ Key Fields: incident_category, incident_date, resolution, police_district                 │
│ ────────────────────────────────────────                                                  │
│ Agent: SFMTA                                                                              │
│ Dataset: Muni Transit Fare Citations                                                      │
│ ID: 8pxu-u28x                                                                             │
│ Key Fields: citation data                                                                 │
│ ────────────────────────────────────────                                                  │
│ Agent: Public Works                                                                       │
│ Dataset: 311 Service Requests                                                             │
│ ID: vw6y-z8j6                                                                             │
│ Key Fields: category, status, opened_date, responsible_agency                             │
│ ────────────────────────────────────────                                                  │
│ Agent: Budget                                                                             │
│ Dataset: City Budget                                                                      │
│ ID: xdgd-c79v                                                                             │
│ Key Fields: fiscal_year, department, revenue_or_spending, budget                          │
│ ────────────────────────────────────────                                                  │
│ Agent: Planning                                                                           │
│ Dataset: Building Permits                                                                 │
│ ID: i98e-djp9                                                                             │
│ Key Fields: permit_type, status, estimated_cost, issued_date                              │
│ Implementation Steps                                                                      │
│                                                                                           │
│ Step 1: Project setup & dependencies                                                      │
│                                                                                           │
│ - Create directory structure                                                              │
│ - requirements.txt: fastapi, uvicorn, httpx, google-genai, python-dotenv, sse-starlette,  │
│ composio                                                                                  │
│ - Update .env with existing keys                                                          │
│                                                                                           │
│ Step 2: Socrata API client (backend/services/socrata.py)                                  │
│                                                                                           │
│ - SocrataClient class using httpx.AsyncClient                                             │
│ - Methods: fetch(dataset_id, query_params) with SoQL support                              │
│ - Built-in $limit, $where, $order helpers                                                 │
│ - Recent-data filtering (last 90 days by default)                                         │
│                                                                                           │
│ Step 3: Gemini LLM service (backend/services/llm.py)                                      │
│                                                                                           │
│ - Use google-genai package                                                                │
│ - analyze_data(agent_name, data_summary, prompt) function                                 │
│ - Returns structured JSON (issue + solution) via Gemini gemini-2.0-flash                  │
│ - System prompt enforces the agent output schema from PRD                                 │
│                                                                                           │
│ Step 4: You.com API service (backend/services/you_api.py)                                 │
│                                                                                           │
│ - Reuse existing you_agent.py pattern                                                     │
│ - search_context(query) for policy precedents and supplementary info                      │
│ - Used by agents when generating solutions                                                │
│                                                                                           │
│ Step 5: Base agent class (backend/agents/base.py)                                         │
│                                                                                           │
│ - CityAgent abstract base with:                                                           │
│   - name, datasets, department, officials (recipients)                                    │
│   - async fetch_data() → calls Socrata client                                             │
│   - async analyze(data) → summarize data, detect issues via Gemini                        │
│   - async generate_solution(issue) → policy recommendation via Gemini                     │
│   - async check_collaborations(all_findings) → keyword/topic overlap detection            │
│   - async run_loop() → 60s marathon loop, publishes to in-memory store                    │
│ - Output follows PRD schema (agent_name, timestamp, issue, solution, evidence)            │
│                                                                                           │
│ Step 6: Implement 5 agents                                                                │
│                                                                                           │
│ Each agent subclass defines:                                                              │
│ - Which datasets to query and how to filter                                               │
│ - Domain-specific analysis prompts for Gemini                                             │
│ - Relevant city officials (name, title, email)                                            │
│ - Severity thresholds                                                                     │
│                                                                                           │
│ SFPD Agent (sfpd.py):                                                                     │
│ - Query recent 90 days of incident reports                                                │
│ - Aggregate by category, detect spikes                                                    │
│ - Officials: Chief of Police, Police Commission                                           │
│                                                                                           │
│ Public Works Agent (public_works.py):                                                     │
│ - Query open 311 cases, group by category                                                 │
│ - Detect backlogs (old unresolved cases)                                                  │
│ - Officials: Director of Public Works                                                     │
│                                                                                           │
│ Budget Agent (budget.py):                                                                 │
│ - Query current fiscal year budget by department                                          │
│ - Compare spending vs appropriations                                                      │
│ - Officials: City Controller, Budget Director                                             │
│                                                                                           │
│ Planning Agent (planning.py):                                                             │
│ - Query recent building permits                                                           │
│ - Track approval rates, processing times                                                  │
│ - Officials: Planning Director                                                            │
│                                                                                           │
│ SFMTA Agent (sfmta.py):                                                                   │
│ - Query transit citation data + supplementary info via You.com                            │
│ - Analyze service patterns                                                                │
│ - Officials: SFMTA Director                                                               │
│                                                                                           │
│ Step 7: Agent orchestrator (backend/main.py)                                              │
│                                                                                           │
│ - FastAPI app with endpoints:                                                             │
│   - GET / → serve static/index.html                                                       │
│   - GET /api/findings → SSE stream of agent findings                                      │
│   - GET /api/findings/latest → JSON of all current findings                               │
│   - POST /api/email/draft → trigger Composio email agent                                  │
│ - On startup: launch all 5 agents as asyncio.create_task                                  │
│ - In-memory findings_store: dict[str, AgentOutput] updated by agents                      │
│ - SSE pushes new findings to connected clients                                            │
│                                                                                           │
│ Step 8: Composio email agent (backend/email_agent.py)                                     │
│                                                                                           │
│ - POST endpoint receives: agent_finding + ngo_name + desired_outcome + context +          │
│ contact_person                                                                            │
│ - Uses Composio SDK to generate email draft                                               │
│ - Returns formatted email with data citations and official addresses                      │
│                                                                                           │
│ Step 9: Frontend dashboard (static/index.html + static/app.js)                            │
│                                                                                           │
│ - Single HTML page with Tailwind CDN                                                      │
│ - Grid of agent cards, each showing:                                                      │
│   - Agent name + department icon                                                          │
│   - Issue title + severity badge (color-coded)                                            │
│   - Key metrics                                                                           │
│   - Solution summary                                                                      │
│   - "View Details" expand                                                                 │
│   - "Draft Email" button → modal with form → calls /api/email/draft                       │
│ - EventSource for SSE, cards update in real-time                                          │
│ - "Last updated X seconds ago" indicator                                                  │
│ - Collaboration indicators when agents share findings                                     │
│                                                                                           │
│ Step 10: Cross-agent collaboration                                                        │
│                                                                                           │
│ - After each agent loop, check other agents' latest findings                              │
│ - Simple keyword/topic matching (e.g., budget agent + any department agent)               │
│ - Generate combined cards with joint analysis via Gemini                                  │
│ - Display linked cards on frontend                                                        │
│                                                                                           │
│ Tech Details                                                                              │
│                                                                                           │
│ - Gemini model: gemini-2.0-flash (15 RPM free tier, fast)                                 │
│ - Socrata: No app token needed for hackathon (throttled but sufficient)                   │
│ - SSE: Use sse-starlette package for server-sent events                                   │
│ - Async: All I/O via httpx.AsyncClient + asyncio                                          │
│ - No DB: In-memory dict for findings store                                                │
│                                                                                           │
│ Verification                                                                              │
│                                                                                           │
│ 1. pip install -r requirements.txt                                                        │
│ 2. python -m uvicorn backend.main:app --reload                                            │
│ 3. Open http://localhost:8000 → dashboard loads                                           │
│ 4. Agent cards appear within 60s with real SF data                                        │
│ 5. Click "Draft Email" → modal → generates email draft                                    │
│ 6. Verify SSE updates by watching cards refresh                                           │
│ 7. Check at least one cross-agent collaboration card appears                              │
╰───────────────────────────────────────────────────────────────────────────────────────────╯

