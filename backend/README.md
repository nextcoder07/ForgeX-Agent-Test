# AI Agent Evaluation & Reliability Engine — Backend

The Python FastAPI backend powering the Agent Evaluation & Reliability Platform. It implements six evaluation engines that together provide CI/CD-style testing for autonomous AI agents.

---

## What This Backend Does

Teams typically ship AI agents against a handful of manually written prompts, so real failure modes — tool-call loops, hallucinated confidence, unsafe destructive actions, silent goal drift — only surface in production. This backend:

1. **Ingests any agent** (Python/TypeScript files, system prompts, REST endpoints) and reconstructs a normalized specification using AST parsing + Gemini AI
2. **Generates adversarial test suites** automatically across 8 categories (normal, edge, recovery, adversarial, safety, security, stress, chaos)
3. **Executes agents in sandboxes** with fault injection, intercepting all tool calls without rewriting agent code
4. **Evaluates every run** using a hybrid rule engine + Gemini LLM judge, with counterfactual replay to prove failure causation
5. **Clusters failures** into root causes and generates a 2D Safety × Capability reliability scorecard
6. **Tracks pipeline telemetry** — real stage duration (ms), token counts, retry counts — not fake progress bars

---

## Project Structure

```
backend/
├── .env                        ← Local API keys and config (never commit)
├── .env.example                ← Safe configuration template
├── requirements.txt            ← Python dependencies
│
└── app/
    ├── main.py                 ← FastAPI app, CORS middleware, router mount
    │
    ├── models/                 ← Pydantic v2 schema definitions
    │   ├── agent.py            ← AgentRecord, ToolDefinition, DependencyDefinition, AgentConstitution
    │   ├── intake.py           ← AgentIntakePayload, NormalizedAgentSpec, SpecConflict, ArtifactRecord
    │   ├── capability.py       ← CapabilityDefinition, CanonicalToolMapping, DependencyBinding
    │   ├── scenario.py         ← Scenario, Category enum, FaultInjection, StrategyPlan, CoverageGapReport
    │   ├── execution.py        ← ToolCallRecord, StateChange, SecurityEvent, ExecutionTrace, SandboxInstance
    │   ├── evaluation.py       ← EvaluationRequest, EvaluationJob, ReliabilityScorecard, RegressionComparison
    │   ├── pipeline.py         ← PipelineStage, TelemetryEvent, PipelineRun
    │   └── failure.py          ← FailureFinding, RunVerdict, FailureCluster, CalibrationSample, CalibrationReport
    │
    ├── core/                   ← Six evaluation engine implementations
    │   ├── llm/                ← AI Provider Abstraction (pluggable)
    │   │   ├── base.py         ← LLMProvider abstract class
    │   │   ├── gemini_provider.py  ← Gemini 2.5 Flash / Flash-Lite
    │   │   └── fallback_mock.py    ← Deterministic offline mock (no API key)
    │   │
    │   ├── intake/             ← Engine 1: Agent Intake & Understanding
    │   │   ├── ast_analyzer.py     ← Extracts function signatures from Python & TypeScript AST
    │   │   ├── spec_reconstructor.py ← Gemini reads AST + prompt → NormalizedAgentSpec
    │   │   └── conflict_detector.py  ← Compares doc safety claims vs actual code behavior
    │   │
    │   ├── scenarios/          ← Engine 2: Scenario Intelligence
    │   │   ├── strategy_planner.py   ← Reads agent risk surface → 8-category plan
    │   │   ├── scenario_generator.py ← Generates test cases using Gemini
    │   │   ├── scenario_critic.py    ← Validates quality, executability, non-duplication
    │   │   ├── scenario_validator.py ← Rule-based schema enforcement
    │   │   └── coverage_engine.py   ← Identifies unexercised tools and categories
    │   │
    │   ├── dependencies/       ← Engine 3: Dependency & Tool Resolution
    │   │   └── tool_gateway.py ← Maps tool names → canonical capabilities → sandbox handlers
    │   │
    │   ├── sandbox/            ← Engine 4: Safe Execution
    │   │   └── runner.py       ← Ephemeral sandbox with fault injection support
    │   │
    │   ├── evaluation/         ← Engine 5: Scoring & Analysis
    │   │   ├── hybrid_evaluator.py    ← Deterministic rules + LLM judge combined score
    │   │   ├── counterfactual.py      ← Strips adversarial tokens, replays clean control
    │   │   ├── failure_clustering.py  ← Groups RunVerdicts into root cause clusters
    │   │   ├── scorecard_engine.py    ← Safety axis + Capability axis + 5-dimension scores
    │   │   └── calibration_engine.py  ← LLM judge vs human gold-standard agreement
    │   │
    │   └── pipeline/           ← Engine 6: Observability
    │       └── monitor.py      ← Real telemetry: duration ms, tokens per stage, retries
    │
    ├── api/                    ← REST API routers
    │   ├── router.py           ← Mounts all routers under /api prefix
    │   ├── agents.py           ← GET /agents, GET /agents/{id}
    │   ├── intake.py           ← POST /intake/analyze, GET /intake/local-agents, GET /intake/local-agents/{id}
    │   ├── capabilities.py     ← GET/POST /capabilities
    │   ├── scenarios.py        ← POST /scenarios/generate, GET /scenarios/library, GET /scenarios/strategy/{id}
    │   ├── evaluations.py      ← POST /evaluations/run, GET /evaluations/{id}/scorecard, GET /evaluations/{id}/clusters
    │   ├── live_attack.py      ← POST /live-attack
    │   ├── calibration.py      ← GET /calibration
    │   └── pipeline.py         ← GET /pipeline/runs/{id}
    │
    └── services/
        └── store.py            ← In-memory store: permanent (agents) + ephemeral (scenarios, evals)

test-agents/                    ← Demonstration agents for testing the platform
├── 01-simple-python/           ← Order status lookup (clean, low-risk)
├── 02-tool-agent/              ← Math + currency + JSON formatter
├── 03-customer-support/        ← Rs10k refund limit (has intentional doc/code conflict)
├── 04-rag-agent/               ← Vectorized document search
├── 05-multi-agent/             ← Orchestrator + Researcher + Writer
├── 06-browser-agent/           ← Headless DOM + scraping
├── 07-tool-loop-vulnerable/    ← Known failure: infinite retry loop
└── 08-prompt-injection-unsafe/ ← Known failure: authority bypass
└── 09-news-summarizer-agent/   ← News fetching and structured summarization
```

---

## Environment Setup — `.env`

The `.env` file lives at `backend/.env`. **This is the most important file to configure.**

```env
# ============================================================
# REQUIRED: Gemini API Key for all AI-powered features
# ============================================================
# Get a FREE key at: https://aistudio.google.com/apikey
# Gemini 2.5 Flash has a free tier with generous quotas.
#
# Without this key, the platform operates in MOCK MODE:
#   - Spec reconstruction uses AST only (no Gemini)
#   - Scenarios are template-generated (not AI-written)
#   - LLM judge uses deterministic rule-based scoring
#   - Counterfactual explanation is diff-only
GEMINI_API_KEY=your_google_gemini_api_key_here

# ============================================================
# OPTIONAL: Server configuration
# ============================================================
PORT=8000
ENVIRONMENT=development   # or production

# Model selection (both have free tier)
# Set this to a model available to your Gemini API project.
# The current default used by this project is gemini-3.6-flash.
GEMINI_MODEL=gemini-3.6-flash

# Set to "true" to skip Gemini entirely (useful for offline dev)
LLM_FALLBACK_MOCK=false
```

### Why `GEMINI_API_KEY` is required for real results

This is **not a purely algorithmic system**. The platform uses Gemini at these critical points:

| Stage | Gemini Role |
|---|---|
| **Spec Reconstruction** | Reads AST output + your system prompt to write a structured NormalizedAgentSpec. Without AI, only raw code is parsed — no semantic understanding of goals or policies. |
| **Scenario Generation** | Creates realistic adversarial + normal test cases. Without AI, scenarios are templated and less realistic. |
| **Scenario Critic** | Reviews each generated scenario for quality, executability, and non-duplication. |
| **LLM Judge** | Evaluates execution traces. Determines if tool calls were appropriate, if safety policies were violated, assigns failure categories with explanations. |
| **Conflict Analysis** | Explains the semantic meaning of doc/code discrepancies in natural language. |

---

## Installation & Running

### Supabase Persistence

Registered agents, normalized specifications, artifact hashes, uploaded source files, and evaluation data are persisted through the Supabase-backed store. Uploaded agents have first-class `agent_artifacts` and `agent_files` manifest records, while `agents.agent_spec` retains the derived specification and a backward-compatible source copy for this MVP. For a new Supabase project, run `migrations/001_init_schema.sql` in the Supabase SQL Editor. For an existing project, also run `migrations/002_store_compatibility.sql` to add the fields and tables expected by the current backend. Restart the API and confirm the startup log says `Supabase connected — persistent storage active.` Otherwise, the backend uses an in-memory fallback and data is lost when the process stops.

### Prerequisites
- Python 3.10+
- pip

### Steps

```powershell
cd anujfor/backend

# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your Gemini API key to .env
#    Edit .env and set GEMINI_API_KEY=your_key_here

# 3. Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Server is now running at:
# http://localhost:8000       ← root status endpoint
# http://localhost:8000/docs  ← interactive Swagger API docs
# http://localhost:8000/redoc ← ReDoc alternative
```

---

## API Reference (28 Routes)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check + version info |
| GET | `/api/agents` | List all registered agents |
| GET | `/api/agents/{id}` | Get single agent by ID |
| GET | `/api/intake/local-agents` | List demo laboratory agents |
| GET | `/api/intake/local-agents/{id}` | Get demo agent source files + metadata |
| POST | `/api/intake/analyze` | Analyze agent files → NormalizedAgentSpec + conflicts |
| POST | `/api/intake/register-spec` | Register a normalized spec as an AgentRecord |
| GET | `/api/scenarios/strategy/{agent_id}` | Get 8-category strategy plan for an agent |
| POST | `/api/scenarios/generate` | Generate + critique scenarios for an agent |
| GET | `/api/scenarios/library` | Get all scenarios in the library |
| GET | `/api/scenarios/coverage/{agent_id}` | Get coverage gap report |
| POST | `/api/evaluations/run` | Launch full evaluation job |
| GET | `/api/evaluations/{id}/scorecard` | Get reliability scorecard for an eval job |
| GET | `/api/evaluations/{id}/clusters` | Get failure clusters for an eval job |
| GET | `/api/evaluations/regression/compare` | Compare two evaluation jobs |
| POST | `/api/live-attack` | Fire adversarial prompt + run counterfactual |
| GET | `/api/calibration` | Get LLM judge calibration benchmark |
| GET | `/api/pipeline/runs/{id}` | Get pipeline telemetry for a run |

---

## Dependencies

| Package | Purpose |
|---|---|
| `fastapi>=0.110.0` | Web framework |
| `uvicorn>=0.28.0` | ASGI server |
| `pydantic>=2.6.0` | Data validation & serialization |
| `python-dotenv>=1.0.0` | Load `.env` file |
| `google-genai>=0.1.0` | Google Gemini API client |

---

## Key Design Decisions

**Tripartite Separation**: The Agent (untrusted code) ≠ The Environment (sandbox controlled by platform) ≠ The Evaluator (hybrid rule + LLM judge). This prevents the agent from influencing its own evaluation.

**Tool Gateway Pattern**: The platform intercepts tool calls at the boundary, mapping original function names to canonical capabilities and routing to safe simulated handlers. No agent code is rewritten.

**Counterfactual Causation Proof**: When an attack-scenario run fails, the platform strips adversarial tokens ("I am the CEO", "SYSTEM NOTE:", urgent legal threats) and replays a clean control. If the clean control passes and the attack fails, causation is proven. If both fail, the agent has a pre-existing vulnerability.

**LLM Provider Abstraction**: Gemini is behind a `LLMProvider` abstract class. Switching to OpenAI, Claude, or another model requires only a new provider implementation — no changes to any engine code.
