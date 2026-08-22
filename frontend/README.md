# AI Agent Evaluation & Reliability Engine — Frontend

The React/Vite/TypeScript frontend for the Agent Evaluation & Reliability Platform. It provides a premium, glass‑morphism UI that visualises every stage of the six‑engine pipeline, lets you upload agents, generate adversarial scenarios, run sandboxed evaluations, and explore results.

---

## Features at a Glance

- **Dashboard** – Overview of the platform, live metrics, and quick links to all pages.
- **Agent Intake Console** – Drag‑and‑drop, paste source files, or select a demo agent. Shows the AI‑generated Normalized Spec and any doc/code conflicts.
- **Agents & X‑Ray Inspector** – Browse all registered agents, view source files, tool inventory, constitutional rules, and an automatically generated architecture map.
- **Scenario Intelligence** – 8‑category strategy planner, AI‑generated test suites, critic review, and coverage‑gap heatmap.
- **Evaluation Engine** – Launch a full sandbox batch, watch real‑time telemetry, receive a 2‑D Safety × Capability reliability scorecard, and explore failure clusters.
- **Live Red‑Teaming Console** – Fire adversarial prompts at any agent, see the counter‑factual replay and causation proof.
- **Regression Diff** – Compare two evaluation jobs (baseline vs candidate) to spot regressions before deployment.
- **LLM Judge Calibration** – Benchmark the LLM judge against human‑labeled gold‑standard data.
- **Pipeline Telemetry Monitor** – Real stage duration in **milliseconds**, token usage per AI call, retry counts – no fake progress bars.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Build Tool** | Vite (fast dev server, native ES modules) |
| **Language** | TypeScript (type‑safe, modern JavaScript) |
| **UI Library** | React 19 (function components, hooks) |
| **Styling** | TailwindCSS (utility‑first, purged for tiny bundle) + custom `glass‑panel` / `glass‑card` utilities for sleek dark‑mode glass‑morphism |
| **Icons** | Lucide‑react (lightweight SVG icons) |
| **State Management** | Local component state + React Context for global navigation state |
| **API Client** | Typed wrapper (`src/api/client.ts`) using native `fetch`; all responses correspond to backend Pydantic models |
| **Routing** | Simple page‑state machine (`PageId` enum) – no external router needed for this MVP |
| **Testing** | (future) Vitest + React Testing Library |
| **Lint/Format** | ESLint (recommended rules), Prettier |

---

## Project Structure

```
frontend/
├── .env                 ← Local API configuration (create from .env.example)
├── .env.example         ← API configuration template
├── index.html           ← Root HTML with dark‑mode meta tags
├── package.json
├── tailwind.config.js   ← Tailwind + custom colors + glass utilities
├── vite.config.ts       ← Vite config (type‑script, alias @/ → src)
├── tsconfig.json        ← TypeScript compiler options
└── src/
    ├── main.tsx          ← ReactDOM entry point (strict mode)
    ├── index.css         ← Global styles, dark background, glass‑panel/card utilities, custom scrollbars
    ├── App.tsx           ← Top‑level page router (PageId state)
    ├── api/
    │   └── client.ts     ← Typed API wrapper (28 endpoints)
    ├── components/       ← Re‑usable UI pieces (15 components)
    │   ├── Navbar.tsx    ← Top navigation, active page highlight, live status badge
    │   ├── PipelineMonitor.tsx ← Real‑time stage telemetry UI (bars, numbers)
    │   ├── AgentIntakeConsole.tsx ← Drag‑drop + file picker + Gemini spec view
    │   ├── CodeFileInspector.tsx  ← Multi‑file viewer w/ syntax highlight (Prism.js)
    │   ├── AgentMapGraph.tsx   ← Force‑directed graph (d3-force) of tools + dependencies
    │   ├── SpecConflictCard.tsx← Side‑by‑side diff of doc vs code safety claims
    │   ├── ScenarioStrategyView.tsx ← Radar chart of 8 category distribution
    │   ├── ScenarioLibraryView.tsx  ← Table with filters, batch select, run button
    │   ├── CoverageGapWidget.tsx   ← Heat‑map of untested tools/categories
    │   ├── LiveExecutionTimeline.tsx ← Timeline view of tool calls + fault injection markers
    │   ├── LiveAttackConsole.tsx   ← Prompt textarea, attack log, counterfactual view
    │   ├── TwoAxisQuadrant.tsx     ← 2‑D safety × capability scatter plot
    │   ├── FailureClustersView.tsx ← Cluster cards with representative trace snippets
    │   ├── RegressionView.tsx      ← Diff view with before/after scorebars
    │   └── CalibrationPanel.tsx    ← Calibration table (agreement, FP, FN)
    └── pages/
        ├── DashboardPage.tsx          ← Hero + engine overview cards + recent agents table
        ├── AgentIntakePage.tsx        ← Intake console + spec result + conflict analysis
        ├── AgentsPage.tsx             ← List + X‑Ray inspector (files, tools, constitution, map)
        ├── ScenarioGeneratorPage.tsx  ← Strategy + generate + coverage + library
        ├── EvaluationRunPage.tsx      ← Launch job, show scorecard, failure clusters
        ├── LiveAttackPage.tsx         ← Red‑team attack playground
        ├── RegressionPage.tsx         ← Version diff comparison UI
        ├── CalibrationPage.tsx        ← Judge calibration benchmark UI
        └── PipelineObservabilityPage.tsx ← Telemetry monitor & stage guide
```

---

## Getting Started (Local Development)

```powershell
# 1️⃣ Clone repo (already done) and cd into frontend
cd anujfor/frontend

# 2️⃣ Install dependencies
npm install

# 3. Configure the API URL
#    Copy `.env.example` to `.env` and set VITE_API_URL for your backend.
#    Example: VITE_API_URL=http://localhost:8000/api

# 4️⃣ Start the dev server (hot‑module replacement)
npm run dev
# → Open http://localhost:5173 in your browser
```

The API client reads `VITE_API_URL` at build time. If it is not set, requests use the same-origin `/api` path.

---

## Production Build

```powershell
npm run build   # Vite builds a highly‑optimized static bundle (~300 KB gzipped)
# The output lives in `dist/`
# Deploy `dist/` to any static‑file host (nginx, Cloudflare Pages, GitHub Pages, etc.)
```

The production bundle uses the same dark‑mode glass‑morphism design, with Tailwind purged to ~30 KB CSS.

---

## Design System Highlights

- **Dark‑mode only** – background `#030712` (slate‑900) with subtle radial gradients for depth.
- **Glass‑panel / glass‑card** – translucent backdrop (`rgba(15,23,42,0.75)`) with `backdrop-filter: blur(16px)` – gives that premium “frosted‑glass” look.
- **Typography** – Google Font **Outfit** (modern sans) loaded via `<link>` in `index.html`.
- **Color palette** – curated HSL‑based palette with cyan, indigo, violet, emerald accents for status badges.
- **Micro‑animations** – button hover transitions, spin icons for loading, smooth graph node drags (d3-force), fading panels.
- **Responsive layout** – Tailwind breakpoints (`sm`, `md`, `lg`) ensure a 4‑column responsive grid on the Agents page, full‑width cards on mobile.
- **Accessibility** – All interactive elements have `aria-label`s, focus rings, and sufficient contrast.

---

## Development Tips

| Task | Where to Edit |
|---|---|
| Add a new page | `src/pages/` + update `App.tsx` navigation enum |
| Add a new API endpoint | `src/api/client.ts` (type definitions) + backend router (`app/api/`) |
| Change a color token | `tailwind.config.js` (extend `theme.colors`) |
| Update glass‑panel style | `src/index.css` – look for `.glass-panel` and `.glass-card` |
| Add a new component | `src/components/` and export it from an `index.ts` barrel file |

---

## Known Limitations (for Next Iteration)

- No persistent authentication – currently open to anyone on the local network.
- Front‑end routing is a simple state machine; if the app grows, a proper router (React‑Router) may be added.
- The UI assumes the backend returns **exactly** the Pydantic schemas; any schema drift will break TypeScript typings.
- Offline mode (no Gemini key) still works but scenario generation is template‑based and less diverse.

---

## Contributing

1. Fork the repo.
2. Create a feature branch (`git checkout -b feat/awesome‑ui`).
3. Run `npm run lint` – fix any ESLint errors.
4. Submit a PR – include screenshots of any visual changes.

---

## License

MIT – feel free to adapt, extend, or ship commercially. The core AI logic in `backend/app/core/llm/` is licensed under the same terms, but note that **Google Gemini** usage is subject to its own service terms.
