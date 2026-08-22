# 🛡️ AI Agent Evaluation & Reliability Engine — Complete Project Plan

> **Project Folder:** `c:\Users\creat\OneDrive\Documents\iforgeu\anujfor\`
> **Stack:** Python FastAPI (backend) + React/Vite/TypeScript (frontend) + Gemini 2.5 Flash (AI engine)

---

## 📌 Project Mission

Autonomous AI agents fail on ~70% of real-world tasks. Teams ship agents against a handful of manually written prompts, so failure modes like tool-call loops, hallucinated confidence, unsafe destructive actions, and silent goal drift only surface after deployment.

**This platform is CI/CD for AI agents** — it automatically generates adversarial test suites, runs sandboxed evaluations, proves failure causation, and produces reliability scorecards before any agent ships.

---

## 🗂️ Complete Project Directory

```
anujfor/
│
├── backend/                        ← Python FastAPI application
│   ├── .env                        ← API keys & environment config (MUST FILL)
│   ├── requirements.txt            ← Python dependencies
│   ├── app/
│   │   ├── main.py                 ← FastAPI entrypoint (CORS, router mount)
│   │   │
│   │   ├── models/                 ← Pydantic data models (schema definitions)
│   │   │   ├── agent.py            ← AgentRecord, ToolDefinition, AgentConstitution
│   │   │   ├── intake.py           ← AgentIntakePayload, NormalizedAgentSpec, ArtifactRecord
│   │   │   ├── capability.py       ← CapabilityDefinition, CanonicalToolMapping
│   │   │   ├── scenario.py         ← Scenario, StrategyPlan, CoverageGapReport
│   │   │   ├── execution.py        ← ExecutionTrace, ToolCallRecord, SecurityEvent
│   │   │   ├── evaluation.py       ← EvaluationJob, ReliabilityScorecard
│   │   │   ├── pipeline.py         ← PipelineRun, PipelineStage, TelemetryEvent
│   │   │   └── failure.py          ← FailureFinding, FailureCluster, CalibrationReport
│   │   │
│   │   ├── core/                   ← Six major evaluation engines
│   │   │   │
│   │   │   ├── llm/                ← AI Provider Abstraction Layer
│   │   │   │   ├── base.py         ← LLMProvider abstract base class
│   │   │   │   ├── gemini_provider.py  ← Gemini 2.5 Flash implementation
│   │   │   │   └── fallback_mock.py   ← Offline mock (no API key needed for dev)
│   │   │   │
│   │   │   ├── intake/             ← Engine 1: Agent Intake & Understanding
│   │   │   │   ├── ast_analyzer.py     ← Python/TS AST parser → extracts tool signatures
│   │   │   │   ├── spec_reconstructor.py ← Gemini reconstructs full NormalizedAgentSpec
│   │   │   │   └── conflict_detector.py  ← Doc claim vs AST code reality diff
│   │   │   │
│   │   │   ├── scenarios/          ← Engine 2: Scenario Intelligence
│   │   │   │   ├── strategy_planner.py   ← Plans 8-category test distribution per agent risk
│   │   │   │   ├── scenario_generator.py ← Generates scenarios using strategy + Gemini
│   │   │   │   ├── scenario_critic.py    ← Critic validates each scenario (Gemini judge)
│   │   │   │   ├── scenario_validator.py ← Rule-based schema & safety validation
│   │   │   │   └── coverage_engine.py   ← Detects unexercised tools & category gaps
│   │   │   │
│   │   │   ├── dependencies/       ← Engine 3: Dependency & Tool Resolution
│   │   │   │   └── tool_gateway.py ← Intercepts tool calls, routes to safe sandbox handlers
│   │   │   │
│   │   │   ├── sandbox/            ← Engine 4: Safe Execution
│   │   │   │   └── runner.py       ← Ephemeral sandbox executor with fault injection
│   │   │   │
│   │   │   ├── evaluation/         ← Engine 5: Evaluation & Reliability Scoring
│   │   │   │   ├── hybrid_evaluator.py    ← Rule engine + Gemini LLM judge combined
│   │   │   │   ├── counterfactual.py      ← Strips attack prefixes, replays clean control
│   │   │   │   ├── failure_clustering.py  ← Groups failures into root cause clusters
│   │   │   │   ├── scorecard_engine.py    ← Computes 2D Safety x Capability scorecard
│   │   │   │   └── calibration_engine.py  ← Judge vs human gold-standard agreement rate
│   │   │   │
│   │   │   └── pipeline/           ← Engine 6: Observability
│   │   │       └── monitor.py      ← Tracks real stage duration ms, tokens, retry counts
│   │   │
│   │   ├── api/                    ← REST API routers (28 routes total)
│   │   │   ├── router.py           ← Mounts all sub-routers under /api
│   │   │   ├── agents.py           ← GET /agents, GET /agents/{id}
│   │   │   ├── intake.py           ← POST /intake/analyze, GET /intake/local-agents
│   │   │   ├── capabilities.py     ← GET/POST /capabilities
│   │   │   ├── scenarios.py        ← POST /scenarios/generate, GET /scenarios/library
│   │   │   ├── evaluations.py      ← POST /evaluations/run, GET /evaluations/{id}/scorecard
│   │   │   ├── live_attack.py      ← POST /live-attack (attack + counterfactual)
│   │   │   ├── calibration.py      ← GET /calibration
│   │   │   └── pipeline.py         ← GET /pipeline/runs/{id}
│   │   │
│   │   └── services/
│   │       └── store.py            ← In-memory data store (agents, scenarios, evals, jobs)
│   │
│   └── test-agents/                ← 8 demonstration agents (known + known-failure)
│       ├── 01-simple-python/       ← Order status lookup agent (Python, clean)
│       ├── 02-tool-agent/          ← Math + currency + JSON formatter agent
│       ├── 03-customer-support/    ← Rs10k refund limit agent (has doc/code conflict)
│       ├── 04-rag-agent/           ← Vectorized document search agent
│       ├── 05-multi-agent/         ← Orchestrator + Researcher + Writer triad
│       ├── 06-browser-agent/       ← Headless DOM & scraping agent
│       ├── 07-tool-loop-vulnerable/ ← Known-failure: infinite retry loop
│       └── 08-prompt-injection-unsafe/ ← Known-failure: authority bypass vulnerability
│
└── frontend/                       ← React + Vite + TypeScript + Tailwind
    ├── .env                        ← Frontend env (VITE_API_URL)
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.tsx                ← ReactDOM root
        ├── App.tsx                 ← Page routing (PageId state machine)
        ├── index.css               ← Design tokens, glass utilities, dark theme
        ├── api/
        │   └── client.ts           ← Complete typed API client (all 28 endpoints)
        ├── components/             ← 15 reusable UI components
        └── pages/                  ← 9 full page assemblies
```

---

## 🔑 Environment Variables (CRITICAL)

### Backend `.env` — `anujfor/backend/.env`

```env
# === REQUIRED FOR AI FEATURES ===
GEMINI_API_KEY=your_google_gemini_api_key_here
# Get free key: https://aistudio.google.com/apikey
# Used for: spec reconstruction, scenario generation, LLM judge, critic

# === OPTIONAL OVERRIDES ===
PORT=8000
ENVIRONMENT=development

# Use gemini-2.5-flash-lite for lower cost / higher throughput
LLM_MODEL=gemini-2.5-flash

# Set to "true" to force offline mock (skips all Gemini calls)
LLM_FALLBACK_MOCK=false
```

> **Without `GEMINI_API_KEY`**: Platform works in mock mode. Scenarios are algorithmic,
> spec reconstruction uses AST only, LLM judge uses rule-based scoring.
> Real AI-quality results require a key.

### Frontend `.env` — `anujfor/frontend/.env`

```env
VITE_API_URL=http://localhost:8000/api
```

---

## 🤖 Where AI (Gemini) Is Used

| Engine Stage | What Gemini Does | Without Key |
|---|---|---|
| Spec Reconstruction | Reads AST output + system prompt, writes NormalizedAgentSpec | Rule-based AST extraction only |
| Scenario Generation | Creates realistic adversarial + normal test cases per category | Template-based generation |
| Scenario Critic | Reviews each scenario for quality, executability, non-duplication | Rule-based schema validation |
| LLM Judge | Evaluates execution traces, assigns pass/fail + failure category | Deterministic rule engine |
| Conflict Analysis | Explains doc/code discrepancies in natural language | Raw diff output only |

---

## 🏗️ Six-Engine Architecture Flow

```
User uploads agent files / pastes code / selects demo
       │
       ▼
ENGINE 1 — Agent Intake & Understanding
  AST parser → Gemini reconstructs → Conflict detector
       │
       ▼
ENGINE 2 — Scenario Intelligence
  Strategy planner → Gemini generator → Critic → Coverage check
       │
       ▼
ENGINE 3 — Dependency & Tool Resolution
  Tool Gateway: intercepts calls → routes to sandbox handlers
       │
       ▼
ENGINE 4 — Sandbox Execution
  Ephemeral instance → Fault injection → Full trace recording
       │
       ▼
ENGINE 5 — Evaluation & Reliability Scoring
  Rule engine + LLM judge → Counterfactual replay → Clustering → 2D Scorecard
       │
       ▼
ENGINE 6 — Results / Observability / History
  Pipeline telemetry → Regression diff → Permanent storage
```

---

## 🌐 Frontend Pages

| Page | What it Shows |
|---|---|
| Dashboard | Platform hero, 6-engine cards, registered agents, live metrics |
| Bring Your Agent | Upload/paste/demo select → spec + conflict analysis + register |
| Agents & X-Ray | Browse agents, inspect source files, tool inventory, architecture map |
| Scenario Library | Strategy plan, generate scenarios, coverage gaps, batch select & run |
| Evaluation Engine | Launch eval job, 2D scorecard, failure clusters |
| Live Attack Console | Fire adversarial prompts, counterfactual causation proof |
| Failure Clusters | Root cause cluster explorer, remediation recommendations |
| Regression Diff | Compare two agent versions, safety/capability deltas |
| Judge Calibration | LLM judge vs human gold-standard agreement rate table |
| Pipeline Monitor | Real-time stage telemetry: duration ms, tokens, retry counts |

---

## 🚀 Quick Start

```powershell
# Terminal 1: Backend
cd anujfor/backend
pip install -r requirements.txt
# Add GEMINI_API_KEY to .env first!
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
cd anujfor/frontend
npm install
npm run dev

# Open: http://localhost:5173
# API docs: http://localhost:8000/docs
```

---

## ✅ Current Build Status

| Component | Status |
|---|---|
| Backend Models (8 files) | COMPLETE |
| Backend Six Engines (20+ files) | COMPLETE |
| Backend API (28 routes) | COMPLETE |
| Test Agent Laboratory (8 agents) | COMPLETE |
| Frontend Build (1840 modules) | COMPLETE — 0 errors |
| Frontend Components (15) | COMPLETE |
| Frontend Pages (9) | COMPLETE |
| `.env` — GEMINI_API_KEY | NEEDS YOUR KEY |
| Backend `pip install` | NEEDS RUN |
