# Product Requirements Document: AI City Council (Hackathon Version)

## 1. Overview

### 1.1 Product Vision
AI City Council is a real-time multi-agent system for SF-based NGOs. Specialized AI agents continuously monitor SF Open Data across city departments, collaboratively analyze civic issues, and surface city-wide solution proposals on a live dashboard. NGOs use Composio agents to draft evidence-based advocacy emails with citations, policy recommendations, and official contact information.

### 1.2 Problem Statement
SF NGOs lack tools to quickly translate government data into actionable advocacy. AI City Council agents work in marathon mode—continuously analyzing data and proposing solutions—while Composio agents help NGOs draft professional emails to city officials.

### 1.3 Success Metrics (Hackathon)
- 4-6 agents running continuously during demo
- Real-time solution proposals updating on frontend
- Composio agent generates emails with data citations and official addresses
- Demonstrate cross-agent collaboration

---

## 2. Agent Selection (4-6 from Original List)

Select agents from:
- **Mayor & Executive Office Agent**
- **Board of Supervisors Agent** 
- **Planning Department Agent**
- **Department of Building Inspection Agent**
- **SFPD Agent**
- **District Attorney Agent**
- **City Attorney Agent**
- **SFMTA Agent**
- **Public Works Agent**
- **Budget & Controller Agent**

**Selection Criteria**:
- High-impact datasets on data.sfgov.org
- Enable compelling advocacy use cases
- Support cross-agent collaboration
- Address urgent SF issues

---

## 3. Agent Architecture

### 3.1 Agent Responsibilities

Each agent must:

**Data Collection**
- Pull relevant datasets from data.sfgov.org via Socrata API
- Use You.com API for context and supplementary information
- Focus on city-wide aggregated data (no district breakdowns)

**Continuous Analysis (Marathon Mode)**
- Run analysis loops every 60 seconds
- Detect issues (e.g., budget gaps, service failures, policy conflicts)
- Calculate metrics relevant to agent domain

**Solution Generation**
- Propose city-wide policy solutions based on data findings
- Identify which city officials should receive advocacy
- Cite specific datasets and evidence

**Frontend Output**
- Publish issue + solution cards to real-time dashboard
- Update findings continuously
- Flag severity level (urgent/moderate/improving)

### 3.2 Agent Output Schema

Each agent produces:

```json
{
  "agent_name": "string",
  "timestamp": "ISO datetime",
  "issue": {
    "title": "string (brief headline)",
    "description": "string (2-3 sentences)",
    "severity": "urgent|moderate|improving",
    "metrics": {
      "key": "value with units"
    }
  },
  "solution": {
    "policy_recommendation": "string (specific action items)",
    "recipients": [
      {
        "name": "Official Name",
        "title": "Position",
        "department": "string",
        "email": "email@sfgov.org"
      }
    ],
    "precedents": ["optional: similar policies in other cities"]
  },
  "evidence": [
    {
      "dataset_name": "string",
      "dataset_url": "data.sfgov.org URL",
      "key_finding": "string"
    }
  ],
  "collaborating_agents": ["list of agent names with relevant data"]
}
```

### 3.3 Cross-Agent Collaboration

Agents must:
- Monitor other agents' outputs for collaboration opportunities
- Combine findings when datasets intersect (e.g., Budget + Planning, SFPD + Public Works)
- Generate joint solution proposals when multi-department coordination needed

**Collaboration Output Schema**:
```json
{
  "collaboration_type": "joint_analysis",
  "participating_agents": ["Agent A", "Agent B"],
  "combined_issue": "string",
  "integrated_solution": "string",
  "cross_referenced_evidence": []
}
```

---

## 4. Composio Email Agent

### 4.1 Trigger
NGO user clicks "Draft Email" button on any agent card on frontend dashboard.

### 4.2 Input Collection

Composio agent collects from user:
1. **NGO Name**: Organization identifier
2. **Desired Outcome**: Specific policy change, budget allocation, meeting request
3. **NGO Context**: Relationship to issue (population served, expertise, urgency factors)
4. **Contact Person**: Name and title for email signature

### 4.3 Email Generation Requirements

Composio agent must draft:

**Email Structure**:
- **Subject Line**: Specific and action-oriented
- **Salutation**: Addressed to correct official(s)
- **Opening**: NGO introduction and credibility establishment
- **Problem Statement**: Issue description with data citations
- **Evidence Section**: Specific metrics from agent findings
- **Policy Request**: Clear, numbered action items from agent solution proposal
- **Urgency/Timeline**: Request for response or meeting
- **Closing**: Professional sign-off with contact information
- **Data Sources Footer**: All dataset URLs cited

**Required Elements**:
- Minimum 2 data citations from agent evidence
- Official recipient email addresses
- Specific policy recommendations (not vague asks)
- Timeline for requested action

### 4.4 Output Format

```json
{
  "email_draft": {
    "subject": "string",
    "to": ["email@sfgov.org"],
    "cc": ["optional additional officials"],
    "body": "string (formatted email text)",
    "data_sources": [
      {
        "dataset": "string",
        "url": "string"
      }
    ]
  },
  "editable": true,
  "copy_to_clipboard": true
}
```

---

## 5. Frontend Dashboard Requirements

### 5.1 Real-Time Agent Display

**Layout**:
- Agent cards in grid or feed layout
- Each card shows: Agent name, Issue title, Key metrics, Solution summary
- Live update indicator (timestamp, "NEW" badge)
- Severity color coding

**Card Actions**:
- "Draft Email" button → triggers Composio agent
- "View Details" → expands full issue + evidence
- "Share Finding" → copy link to specific agent discovery

### 5.2 Update Mechanism
- Frontend polls backend every 30-60 seconds OR
- Server-sent events (SSE) for real-time push
- Display "Last updated: X seconds ago"

### 5.3 Collaboration Indicators
- When agents collaborate, show linked cards
- Visual connection between related findings
- Combined solution proposals highlighted

---

## 6. Technology Stack

### 6.1 Required Components

**Backend**:
- Python FastAPI (API server)
- You.com API integration (web search, data context)
- Socrata API client (data.sfgov.org)
- LangChain (agent orchestration)
- Composio integration (email drafting)

**Frontend**:
- React/Next.js (real-time updates)
- Tailwind CSS (styling)
- Basic data visualization (charts/graphs)

**Data Storage**:
- JSON files or lightweight DB for agent state
- Cache for API responses

**Deployment**:
- Frontend: Vercel
- Backend: Railway/Render/similar

### 6.2 API Integrations

**You.com API** - Use for:
- Contextual information about SF policies
- Supplementary data when data.sfgov.org incomplete
- Policy precedents from other cities

**Socrata API (data.sfgov.org)** - Use for:
- Primary dataset retrieval
- Structured civic data
- Real-time or near-real-time datasets where available

**Composio** - Use for:
- Email drafting workflow
- Template management
- Output formatting

---

## 7. Data Sources

### 7.1 Primary Source
All agents pull from **data.sfgov.org** (Socrata open data portal)

### 7.2 Dataset Categories by Agent

**Budget & Controller Agent**:
- Departmental expenditures
- Budget appropriations
- Audit reports

**Board of Supervisors Agent**:
- Legislation (ordinances, resolutions)
- Voting records
- Committee hearings

**Planning Department Agent**:
- Building permits
- Zoning changes
- CEQA reviews

**SFPD Agent**:
- Crime incident reports
- Response times
- Staffing data

**SFMTA Agent**:
- Muni performance metrics
- Service changes
- Ridership data

**Public Works Agent**:
- 311 service requests
- Infrastructure maintenance
- Street resurfacing

**Mayor & Executive Office Agent**:
- Executive directives
- Budget proposals
- Departmental appointments

**Department of Building Inspection Agent**:
- Permit applications
- Code enforcement
- Inspection records

**District Attorney Agent**:
- Charging data
- Case dispositions
- Diversion programs

**City Attorney Agent**:
- Litigation records
- Settlements
- Legal opinions

### 7.3 Data Refresh
- Agents check for updated datasets every analysis loop
- Use dataset "last modified" timestamp to detect changes
- Handle API rate limits appropriately

---

## 8. Workflow Specification

### 8.1 Agent Marathon Loop

```
LOOP (every 60 seconds):
  1. Fetch latest data from assigned datasets
  2. Run analysis algorithms
  3. Detect issues (threshold-based or anomaly detection)
  4. Generate solution proposal
  5. Check for cross-agent collaboration opportunities
  6. Publish output to frontend API
  7. Log findings
END LOOP
```

### 8.2 NGO Email Drafting Workflow

```
1. NGO views agent finding on dashboard
2. NGO clicks "Draft Email"
3. Composio agent prompts for:
   - NGO name
   - Desired outcome
   - NGO context
   - Contact person
4. Composio generates email with:
   - Agent issue summary
   - Data citations
   - Policy recommendations
   - Official recipients
5. NGO reviews/edits draft
6. NGO copies email for sending
```

### 8.3 Cross-Agent Collaboration Workflow

```
Agent A publishes finding →
Agent B detects related dataset/issue →
Agents coordinate to produce joint analysis →
Combined solution card appears on frontend →
Composio email includes multi-department coordination plan
```

---

## 9. Output Requirements

### 9.1 Agent Solution Proposals

Must include:
- **Specific policy recommendation** (not vague suggestions)
- **Responsible officials** with contact information
- **Implementation timeline** estimate
- **Budget implications** (if relevant)
- **Success metrics** (how to measure if solution works)

### 9.2 Email Drafts

Must include:
- **Professional tone** appropriate for government officials
- **Clear ask** (specific action requested)
- **Evidence-based argumentation** (minimum 2 data citations)
- **Actionable timeline** (response requested by X date)
- **Contact information** for follow-up

### 9.3 Data Citations

Format:
```
Dataset Name: SF Crime Incident Reports
Source: https://data.sfgov.org/d/wg3w-h783
Last Updated: YYYY-MM-DD
Key Finding: "Metric X increased by Y%"
```

---

## 10. Success Criteria

### 10.1 Technical Performance
- Agent analysis loops complete in <30 seconds
- Frontend updates within 60 seconds of agent output
- Zero data API errors during demo
- Composio email generation in <10 seconds

### 10.2 Demo Requirements
- Minimum 4 agents running simultaneously
- At least 1 cross-agent collaboration demonstrated
- Generate 3+ email drafts during demo
- All emails include real data citations and official addresses

### 10.3 User Experience
- NGO can draft email in <3 minutes total
- Solution proposals are actionable (not generic)
- Data visualizations clearly communicate issues
- Email drafts require minimal editing

---

## 11. Constraints & Assumptions

### 11.1 Hackathon Constraints
- Development time: 24-48 hours
- No user authentication required
- No actual email sending (draft only)
- City-wide analysis only (no geographic granularity)

### 11.2 Assumptions
- data.sfgov.org API availability and stability
- You.com API quota sufficient for hackathon
- Composio supports template-based email generation
- NGO users familiar with SF government structure

### 11.3 Out of Scope
- Historical trend analysis (focus on recent 3-6 months)
- Predictive modeling
- Multi-city support
- Mobile application
- Email tracking/delivery confirmation

---

## 12. Implementation Notes for Agent Developers

### 12.1 Agent Development Checklist
- [ ] Identify 5-10 key datasets from data.sfgov.org
- [ ] Define issue detection logic (thresholds, anomalies)
- [ ] Create solution template (policy recommendations)
- [ ] Map official recipients (names, titles, emails)
- [ ] Implement analysis loop (60s cycle)
- [ ] Test output schema compliance
- [ ] Implement collaboration detection logic

### 12.2 Code Structure Guidance
```python
class CityAgent:
    def __init__(self, agent_name, datasets):
        self.name = agent_name
        self.datasets = datasets
        self.last_update = None
    
    def fetch_data(self):
        # Pull from data.sfgov.org
        pass
    
    def analyze(self):
        # Run analysis, detect issues
        pass
    
    def generate_solution(self):
        # Create policy recommendation
        pass
    
    def check_collaborations(self, other_agents):
        # Detect cross-agent opportunities
        pass
    
    def publish_output(self):
        # Send to frontend API
        pass
    
    def run_marathon(self):
        while True:
            self.fetch_data()
            issue = self.analyze()
            solution = self.generate_solution()
            self.check_collaborations()
            self.publish_output()
            time.sleep(60)
```

### 12.3 Composio Integration Notes
- Use Composio's email template system
- Inject agent findings into template variables
- Validate recipient email format
- Include data source footer in all emails

---

**Document Version**: 1.0 (Hackathon)  
**Target Use Case**: SF-based NGO advocacy  
**Tech Stack**: You.com + Composio + data.sfgov.org  
**Expected Agents**: 4-6 from original department list