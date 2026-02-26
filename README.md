# FDIR System

This repository contains the Fault Detection, Isolation, and Recovery (FDIR) backend + dashboard.

See:

- [FDIR/README.md](FDIR/README.md)
# 🛡️ Advanced Disaster Response Decision-Support System (DSS)

> **Enterprise-grade, explainable, human-in-the-loop disaster response system**  
> Academic demonstration of responsible AI governance in critical decision-making

---

## 🎯 Overview

This system demonstrates **advanced decision-support architecture** for disaster response, emphasizing:

- **Multi-source data fusion** with confidence tracking
- **Explainable risk assessment** using hazard-exposure-vulnerability framework
- **Human-in-the-loop enforcement** — NO autonomous execution
- **Governance gate** with mandatory approval requirements
- **Immutable audit trail** for full traceability

**This is NOT production software** — uses mock data only for academic demonstration.

---

## Spacecraft FDIR Demo (Deterministic)

This repo also contains a deterministic spacecraft **Autonomous FDIR** demo with an ethical autonomy gate.

Run from repo root:

- Backend: `python main.py` (FastAPI on `http://localhost:8001`, WebSocket at `/ws`)
- Frontend: `npm install` then `npm run dev` (Next.js on `http://localhost:3000`)

See [FDIR/README.md](FDIR/README.md) for details.

---

## 🏗 System Architecture

### Layered Backend Design

```
backend/
├── api/routes/              # API endpoint handlers
│   ├── data_ingestion.py    # Multi-source data intake
│   ├── decision_routes.py   # Risk & decision endpoints
│   ├── governance_routes.py # Human approval enforcement
│   └── audit_routes.py      # Audit trail access
│
├── services/                # Business logic orchestration
│   └── disaster_response_service.py
│
├── engines/                 # Core algorithms
│   ├── data_fusion_engine.py        # Multi-source integration
│   ├── risk_assessment_engine.py    # Explainable risk calculation
│   └── decision_option_engine.py    # Response synthesis
│
├── governance/              # Human-in-the-loop enforcement
│   └── governance_gate.py   # Approval requirement logic
│
├── repositories/            # Data access layer
│   └── database.py          # SQLite operations
│
├── audit/                   # Traceability system
│   └── audit_logger.py      # Immutable event logging
│
├── models/                  # Data schemas
│   └── schemas.py           # Pydantic models
│
└── demo/                    # Demo scenarios
    └── scenarios.py         # Mock data loaders
```

### Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND UI                             │
│  Situational Dashboard | Decision Comparison | Governance Panel  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API LAYER                               │
│  /ingest/* | /risk/assessment | /decision/packages | /audit/*   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVICE LAYER                              │
│           DisasterResponseService (orchestration)                │
└────────┬───────────┬───────────┬────────────┬───────────────────┘
         │           │           │            │
         ▼           ▼           ▼            ▼
┌────────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────────────┐
│ Data Fusion│ │   Risk    │ │ Decision │ │   Governance Gate    │
│   Engine   │ │ Assessment│ │  Option  │ │ (Human-in-the-Loop)  │
│            │ │  Engine   │ │  Engine  │ │                      │
└────────────┘ └───────────┘ └──────────┘ └──────────────────────┘
         │           │           │            │
         └───────────┴───────────┴────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  AUDIT LOGGER (Immutable)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DATABASE (SQLite)                             │
│  ingested_data | risk_assessments | decisions | audit_trail     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧠 Core Components

### 1. Data Fusion Engine

**Purpose:** Integrate heterogeneous data sources into unified region state

**Features:**
- Accepts weather, satellite, population, field report data
- Tracks per-source confidence scores
- Identifies data gaps and uncertainty
- Outputs `FusedRegionState` with uncertainty flags

**Example Output:**
```json
{
  "region": "Coastal Zone A",
  "signals": {
    "rainfall": 245,
    "flood_extent": 78,
    "population_density": 8900
  },
  "source_confidence": {
    "weather": 0.83,
    "satellite": 0.70,
    "population": 0.92
  },
  "data_completeness": 0.89,
  "uncertainty_flags": ["No field report validation"]
}
```

---

### 2. Risk Assessment Engine

**Purpose:** Explainable risk calculation using hazard-exposure-vulnerability framework

**Algorithm:**
```
Risk Score = Hazard × Exposure × Vulnerability
Confidence = f(data_completeness, source_confidence, uncertainty_penalties)
```

**Features:**
- Deterministic thresholds (no ML black box)
- Structured reasoning graph generation
- Confidence penalties for missing/uncertain data
- Risk level downgrading when confidence is low

**Example Output:**
```json
{
  "region": "Coastal Zone A",
  "risk_level": "CRITICAL",
  "risk_score": 0.87,
  "confidence": 0.72,
  "reasoning_graph": [
    "Rainfall (245 mm) exceeds historical threshold (180 mm)",
    "Severe flood extent: 78% of region submerged",
    "High population density: 8900/km² in hazard zone",
    "Critical water level: 9.8m (danger threshold exceeded)",
    "⚠ Confidence reduced: No field report validation"
  ],
  "components": {
    "hazard": 0.91,
    "exposure": 0.85,
    "vulnerability": 0.62
  }
}
```

---

### 3. Decision Option Engine

**Purpose:** Synthesize response options with transparent trade-offs

**Features:**
- Generates 3-5 options per risk level
- Each option includes:
  - Expected benefit
  - Tradeoffs (risks/costs)
  - Irreversibility rating (LOW/MEDIUM/HIGH)
  - Ethical sensitivity (LOW/MEDIUM/HIGH)
  - Confidence score

**Example Options:**
- **Full Evacuation** (HIGH irreversibility, HIGH ethics)
- **Targeted Evacuation** (MEDIUM irreversibility, MEDIUM ethics)
- **Shelter-in-Place** (LOW irreversibility, MEDIUM ethics)
- **Relief Pre-positioning** (LOW irreversibility, LOW ethics)

---

### 4. Governance Gate ⚠️ **CRITICAL**

**Purpose:** Enforce human-in-the-loop — prevent autonomous execution

**Decision Rules:**
1. **HIGH/CRITICAL risk → APPROVAL_REQUIRED**
2. **Low confidence (<0.65) → APPROVAL_REQUIRED**
3. **Insufficient data (<60%) → REQUEST_MORE_DATA**
4. **High irreversibility options → APPROVAL_REQUIRED**
5. **Ethically sensitive actions → APPROVAL_REQUIRED**
6. **Multiple uncertainty flags → ESCALATE**
7. **DEFAULT: All decisions require approval**

**Example Output:**
```json
{
  "status": "APPROVAL_REQUIRED",
  "requires_human_approval": true,
  "reason": "Risk level HIGH requires human approval; High-irreversibility options present",
  "confidence_threshold_met": false,
  "data_sufficiency": true
}
```

**Hard-coded principle:**
```python
def can_proceed_without_approval(self) -> bool:
    return False  # ALWAYS requires human approval
```

---

### 5. Audit Trail System

**Purpose:** Immutable record of all system actions

**Events Logged:**
- `DATA_INGESTION` — Every data point ingested
- `RISK_ASSESSMENT` — Risk calculations with reasoning
- `DECISION_SYNTHESIS` — Options generated
- `GOVERNANCE_CHECK` — Governance gate decisions
- `HUMAN_APPROVAL` — Human approvals (THE ONLY WAY TO EXECUTE)

**Guarantees:**
- **Immutable** — Cannot be modified after creation
- **Complete** — Every decision has full context
- **Traceable** — Data → Reasoning → Decision → Human Action

---

## 🎮 Demo Scenarios

### Demo Mode 1: Comprehensive Flood Scenario

**Button:** `⚡ Load Flood Scenario`

**Loads:**
- **Coastal Zone A** — CRITICAL risk (extreme rainfall, severe flooding, high population)
- **Riverside District** — MEDIUM risk (moderate indicators)
- **Hillside Region** — LOW risk (minimal hazard)
- **Industrial Park** — HIGH risk with UNCERTAINTY (missing satellite data)

### Demo Mode 2: Conflicting Reports

**Button:** `🔀 Conflicting Reports`

**Demonstrates:**
- Weather data shows high rainfall (220mm)
- Satellite shows minimal flooding (12%)
- Field report claims severe flooding (75%)
- **System handles conflict** by downgrading confidence and flagging uncertainty

### Demo Mode 3: Inject Uncertainty

**Button:** `⚠ Inject Uncertainty`

**Action:** Adds low-confidence conflicting data for selected region

**Shows:** How system responds to data quality issues

---

## 🚀 Installation & Usage

### Prerequisites

- Python 3.11+
- Node.js 18+

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend runs at: `http://localhost:8000`  
API docs: `http://localhost:8000/docs`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: `http://localhost:3000`

---

## 📋 Demo Walkthrough Script

### Step 1: Launch System

1. Start backend (port 8000)
2. Start frontend (port 3000)
3. Open `http://localhost:3000` in browser

### Step 2: Load Data

1. Click **"⚡ Load Flood Scenario"**
2. System ingests data for 4 regions
3. Automatically switches to **Situational Dashboard**

### Step 3: Situational Awareness

1. View color-coded risk cards for each region
2. Note confidence meters and uncertainty warnings
3. Click **"▶ Why this risk?"** to expand reasoning graph
4. Observe how **Industrial Park** has reduced confidence due to missing satellite data

### Step 4: Decision Comparison

1. Click on any region's **"View Decision Options →"** button
2. Review 3-5 response options side-by-side
3. Examine:
   - Benefit vs Tradeoffs
   - Irreversibility ratings
   - Ethical sensitivity
   - Confidence scores

### Step 5: Governance Panel

1. Switch to **"Governance"** tab
2. Observe governance status for all regions
3. Note that **ALL require human approval**
4. Read governance reasons (e.g., "Risk level HIGH requires human approval")

### Step 6: Human Approval

1. Return to **Decision Comparison** tab
2. Select an option (e.g., "Full Evacuation" for Coastal Zone A)
3. Click **"APPROVE DECISION"** button
4. ✓ Action is logged to audit trail

### Step 7: Audit Trail

1. Switch to **"Audit Trail"** tab
2. View complete event log
3. Filter by event type
4. Expand records to see full payload
5. Confirm: **Human Approvals: N** | **Autonomous Actions: 0**

### Step 8: Uncertainty Handling (Demo)

1. Return to **Dashboard**
2. Select a region (e.g., Coastal Zone A)
3. Click **"⚠ Inject Uncertainty"**
4. Observe how confidence drops and governance flags change

### Step 9: Conflicting Reports (Demo)

1. Click **"🔀 Conflicting Reports"**
2. New region "Disputed Zone" appears
3. Note low confidence due to source disagreement
4. System downgrades risk level and requires additional data

---

## 🔐 Governance Principles (Human-in-the-Loop)

This system **NEVER** executes decisions autonomously. The governance gate enforces:

1. ✅ **All decisions require human approval** (no exceptions)
2. ✅ **High-risk situations escalate automatically**
3. ✅ **Low confidence triggers data requests**
4. ✅ **Irreversible actions get heightened scrutiny**
5. ✅ **Ethical considerations are flagged explicitly**
6. ✅ **Uncertainty prevents premature action**

**Code-level enforcement:**
```python
def can_proceed_without_approval(self) -> bool:
    return False  # Hard-coded — cannot be overridden
```

---

## 📊 API Endpoints

| Method | Endpoint                  | Description                          |
|--------|---------------------------|--------------------------------------|
| POST   | `/ingest/weather`         | Ingest weather data                  |
| POST   | `/ingest/satellite`       | Ingest satellite imagery data        |
| POST   | `/ingest/population`      | Ingest population/demographic data   |
| POST   | `/ingest/field_report`    | Ingest ground team reports           |
| GET    | `/risk/assessment`        | Get explainable risk assessments     |
| GET    | `/decision/packages`      | Get decision options + governance    |
| GET    | `/governance/status`      | Get governance gate status           |
| POST   | `/governance/approve`     | **HUMAN APPROVAL** (only execution path) |
| GET    | `/audit/trail`            | Get immutable audit log              |
| GET    | `/audit/summary`          | Get audit statistics                 |
| POST   | `/demo/load-scenario`     | Load comprehensive flood scenario    |
| POST   | `/demo/inject-uncertainty`| Inject data uncertainty (demo)       |
| POST   | `/demo/conflicting-reports`| Load conflicting data scenario      |

---

## 🧪 Technical Stack

| Layer          | Technology             |
|----------------|------------------------|
| Backend        | Python, FastAPI        |
| Database       | SQLite                 |
| Validation     | Pydantic               |
| Frontend       | React (Vite)           |
| Styling        | Tailwind CSS           |
| Architecture   | Layered (services/engines/governance) |

---

## ⚠️ Disclaimer

This is an **academic demonstration system**:

- ❌ Does NOT use real data
- ❌ Does NOT connect to external APIs
- ❌ Does NOT execute real-world actions
- ❌ Does NOT use machine learning
- ✅ Uses mock scenarios only
- ✅ Demonstrates governance principles
- ✅ Shows explainable reasoning
- ✅ Enforces human-in-the-loop

---

## 📚 Project Alignment

This system demonstrates concepts from:

- **Multi-source data fusion** (sensor fusion, confidence tracking)
- **Explainable AI** (reasoning graphs, transparent logic)
- **Human-AI collaboration** (governance gates, approval workflows)
- **Responsible AI governance** (audit trails, accountability)
- **Risk assessment frameworks** (hazard-exposure-vulnerability)
- **Decision support systems** (option synthesis, trade-off analysis)

---

## 🎓 Academic Use

Suitable for demonstrations of:

- AI governance and ethics
- Decision-support system design
- Human-in-the-loop architectures
- Explainable AI techniques
- Crisis management systems
- Software engineering best practices

---

**Built for academic demonstration — Shows how AI systems CAN and SHOULD work in high-stakes domains**

