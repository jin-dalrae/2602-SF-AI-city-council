# AI City Council - Real-Time Civic Advocacy 🏛️🤖

AI City Council is a real-time multi-agent system designed for SF-based NGOs. Specialized AI agents continuously monitor San Francisco Open Data, collaborate to analyze civic issues, and surface policy recommendations on a live dashboard. It bridges the gap between raw government data and actionable advocacy.

## 🚀 Key Features

- **Continuous Marathon Mode**: Agents run analysis loops every 60 seconds to detect budget gaps, service failures, and policy conflicts in real-time.
- **Multi-Agent Collaboration**: Specialized agents (SFPD, SFMTA, Public Works, Planning, Budget) coordinate to identify cross-departmental solutions.
- **Data-Driven Advocacy**: Integrates with **Composio** and **You.com** to draft evidence-based advocacy emails to city officials with verified citations.
- **Real-Time Dashboard**: A live feed of agent findings, severity alerts, and policy proposals.
- **Agent Evolution**: Agents utilize episodic memory and self-evolution traits to improve analysis quality over time.

## 🛠️ Tech Stack

- **Backend**: Python (FastAPI), LangChain, Composio
- **AI Models**: Google Gemini 2.0 Flash (Analysis & Generation)
- **Data Sources**: Socrata API (data.sfgov.org), You.com API (Context & News)
- **Frontend**: React/Next.js with SSE (Server-Sent Events) for real-time updates

## 📂 Project Structure

- `/backend`: Core logic, agent implementations, and services.
  - `/agents`: Domain-specific agents (Police, Transit, Public Works, etc.).
  - `/services`: API wrappers for Socrata, Gemini, and You.com.
- `/static`: Frontend dashboard assets.
- `PRD.md`: Original product vision and requirements.
- `implementation.md`: Technical execution plan.

## 🚦 Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Environment Setup**:
   Configure your `.env` file with Gemini, You.com, and Composio API keys.
3. **Run the Application**:
   ```bash
   python -m uvicorn backend.main:app --reload
   ```
4. **Access the Dashboard**:
   Open `http://localhost:8000` in your browser.

## 📊 Current Agents

- **SFPD Agent**: Monitors crime incident reports and staffing.
- **SFMTA Agent**: Analyzes transit performance and service patterns.
- **Public Works Agent**: Tracks 311 service requests and infrastructure backlogs.
- **Budget Agent**: Compares departmental spending vs. appropriations.
- **Planning Agent**: Monitors building permits and processing times.

---
*Built for SF NGOs to turn open data into civic action.*
