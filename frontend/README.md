# 🛡️ ForgeX Agents — Frontend

The React 18 / Vite / TypeScript frontend for **ForgeX Agents** (Autonomous AI Agent Reliability, Evaluation & Self-Healing Engine).

- 🌐 **Live Web Application**: [**forge-agent.netlify.app**](https://forge-agent.netlify.app)
- 🚀 **Platform**: **ForgeX Agents**

---

## Features at a Glance

- **Dashboard** – Overview of ForgeX Agents platform, live metrics, and engine timeline.
- **Agent Intake Console** – Drag-and-drop source files or select demo agents. Displays AI-reconstructed specifications and doc-code conflict analysis.
- **Agents & X-Ray Inspector** – Browse registered agents, inspect source files, tool inventory, constitutional rules, and AST dependencies.
- **Scenario Intelligence** – 8-category strategy planner, AI-generated test suites, critic review, and coverage-gap engine.
- **Dependency & Setup Control** – 12-step setup orchestrator, preflight ping tests, system credential vault, and 3 execution modes (`Faithful`, `Compatible`, `Simulation`).
- **Sandboxed Execution Engine** – Launch sandbox evaluation jobs, monitor real-time waterfall telemetry, and inspect circuit-breaker logs.
- **Dual-Layer Results & Scorecards** – 2D Safety × Capability matrix, deterministic assertion rules, calibrated LLM judge, and failure cause clustering.
- **Stage 6: Improve & Self-Healing** – Evidence-grounded failure diagnosis, safety-gated code/prompt repair, regression diff matrix, and SFT/DPO dataset studio.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Live Web App** | [forge-agent.netlify.app](https://forge-agent.netlify.app) |
| **Build Tool** | Vite (fast dev server, native ES modules) |
| **Language** | TypeScript 5 (type-safe, modern contracts) |
| **UI Library** | React 18 (functional components, hooks) |
| **Styling** | TailwindCSS 3.4 + Custom Dark System (`#020817` base, glass-morphism panels) |
| **Icons** | Lucide-react (lightweight SVG icons) |
| **Routing** | React Router v6 |
| **API Client** | Typed wrapper (`src/api/client.ts`) matching backend FastAPI schemas |

---

## Project Structure

```
frontend/
├── .env                 ← Local API configuration (VITE_API_URL=http://localhost:8000/api)
├── .env.example         ← API configuration template
├── index.html           ← Root HTML with dark-mode meta tags
├── package.json
├── tailwind.config.js   ← Tailwind styling configuration
├── vite.config.ts       ← Vite build configuration
└── src/
    ├── main.tsx          ← React entrypoint
    ├── index.css         ← Global styles, keyframe animations, card/btn design system
    ├── App.tsx           ← Central router & layout wrapper
    ├── api/
    │   └── client.ts     ← Typed API wrapper matching backend models
    ├── components/       ← UI components
    │   ├── Navbar.tsx    ← Navigation bar, platform logo, user dropdown
    │   ├── LiveProcessMonitor.tsx ← Real-time execution telemetry monitor
    │   ├── CoverageGapWidget.tsx  ← Heatmap & un-tested surface gap detector
    │   └── ScenarioStrategyView.tsx ← Category distribution & strategy planner
    └── pages/
        ├── DashboardPage.tsx       ← Platform overview, hero mesh, KPI cards
        ├── AgentsPage.tsx          ← Agent catalog, intake stepper & AST inspector
        ├── ScenarioGeneratorPage.tsx ← Scenario intelligence & 8-category generator
        ├── DependencySetupPage.tsx ← Setup Control Center & credential vault
        ├── ExecutionPage.tsx       ← Sandboxed execution control & trace timeline
        ├── EvaluationRunPage.tsx   ← Dual-layer scorecard & 2D matrix
        ├── ImprovePage.tsx         ← Failures diagnosis, repairs, regression & dataset studio
        ├── LoginPage.tsx           ← Authentication portal
        └── SignupPage.tsx          ← Workspace registration portal
```

---

## Getting Started (Local Development)

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Configure local environment
# Copy .env.example to .env
# Set VITE_API_URL=http://localhost:8000/api

# 4. Start local development server
npm run dev
# → Open http://localhost:5173 in your browser
```

---

## Production Deployment (Netlify)

The production web app is deployed on **Netlify** at [**https://forge-agent.netlify.app**](https://forge-agent.netlify.app).

To build and deploy locally or to Netlify:

```bash
npm run build   # Builds production static bundle into `dist/`
```

### Environment Variables for Deployment:
- `VITE_API_URL`: URL of the deployed ForgeX FastAPI backend (e.g., `https://your-backend-domain.com/api`).
- `VITE_FIREBASE_PROJECT_ID`: Firebase project ID for workspace authentication.
- `VITE_SUPABASE_URL`: Supabase project URL for frontend data persistence.
