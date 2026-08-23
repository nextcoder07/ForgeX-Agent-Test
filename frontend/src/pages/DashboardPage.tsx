import React, { useState, useEffect } from 'react';
import { fetchAgents, fetchScenarioLibrary, fetchCalibrationReport } from '../api/client';
import type { AgentRecord, Scenario, CalibrationReport } from '../api/client';
import { Activity, ShieldCheck, Layers, Cpu, Flame, ArrowRight, Sparkles, GitCompare, CheckCircle2, TrendingUp, RefreshCw, Radio } from 'lucide-react';
import type { PageId } from '../components/Navbar';

interface DashboardPageProps {
  onNavigate: (page: PageId) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [calibration, setCalibration] = useState<CalibrationReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      fetchAgents().then(setAgents),
      fetchScenarioLibrary().then(setScenarios),
      fetchCalibrationReport().then(setCalibration),
    ]).finally(() => setLoading(false));
  }, []);

  const categories = [...new Set(scenarios.map(s => s.category))];
  const validatedScenarios = scenarios.filter(s => s.validation_status === 'VALIDATED');

  const engineSteps = [
    { id: 'intake', label: 'Agent Intake & Understanding', description: 'Upload or select any agent. AST static analysis + Gemini-powered spec reconstruction maps tools, goals, and policy claims.', icon: Sparkles, color: 'from-cyan-500 to-cyan-700', page: 'intake' as PageId },
    { id: 'scenarios', label: 'Scenario Intelligence Engine', description: 'Auto-generates 8-category adversarial + normal test suites. Critic validates each scenario before it enters the library.', icon: Layers, color: 'from-indigo-500 to-indigo-700', page: 'scenarios' as PageId },
    { id: 'evaluations', label: 'Sandbox + Evaluation Engine', description: 'Runs agents in ephemeral sandboxes with fault injection. Hybrid rule + LLM judge scores every run. Counterfactual replay isolates causation.', icon: ShieldCheck, color: 'from-violet-500 to-violet-700', page: 'evaluations' as PageId },
    { id: 'live-attack', label: 'Live Red-Teaming Console', description: 'Fire real-time adversarial prompts. Instant counterfactual replay compares agent response against clean control.', icon: Flame, color: 'from-rose-500 to-rose-700', page: 'live-attack' as PageId },
    { id: 'failures', label: 'Failure Clustering & Causation', description: 'ML clustering groups similar failures into root cause clusters with remediation recommendations.', icon: Activity, color: 'from-amber-500 to-amber-700', page: 'failures' as PageId },
    { id: 'scorecard', label: 'Regression & Version Diff', description: 'Compare two agent versions with safety/capability delta. Detect regressions before deploying updates.', icon: GitCompare, color: 'from-emerald-500 to-emerald-700', page: 'scorecard' as PageId },
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-3xl p-8 border border-slate-800 bg-gradient-to-br from-slate-950 via-indigo-950/40 to-slate-950 shadow-2xl">
        {/* Glowing BG */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-4 left-1/3 w-72 h-72 bg-cyan-600/8 rounded-full blur-3xl" />
          <div className="absolute bottom-4 right-1/4 w-56 h-56 bg-indigo-600/8 rounded-full blur-3xl" />
        </div>

        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-3">
            <div className="flex items-center space-x-3">
              <span className="px-2.5 py-1 text-[10px] font-mono uppercase rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 tracking-widest">
                AI Reliability CI Platform
              </span>
            </div>
            <h1 className="text-3xl font-extrabold text-slate-100 leading-tight">
              Agent Evaluation &<br />
              <span className="bg-gradient-to-r from-cyan-400 via-indigo-400 to-rose-400 bg-clip-text text-transparent">
                Reliability Engine
              </span>
            </h1>
            <p className="text-slate-400 text-sm max-w-lg leading-relaxed">
              Autonomous AI agents fail on ~70% of real-world tasks. This platform provides continuous integration for agents — automatically generating adversarial test suites, running sandboxed evaluations, proving failure causation, and producing reliability scorecards before you ship.
            </p>

            <div className="flex items-center space-x-3 pt-2 flex-wrap gap-2">
              <button
                onClick={() => onNavigate('intake')}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-rose-600 hover:from-cyan-400 hover:to-rose-500 text-slate-100 font-bold text-sm shadow-lg shadow-cyan-500/20 flex items-center space-x-2 transition"
              >
                <Sparkles className="w-4 h-4" />
                <span>Bring Your Agent</span>
              </button>
              <button
                onClick={() => onNavigate('live-attack')}
                className="px-5 py-2.5 rounded-xl bg-rose-950/50 hover:bg-rose-950/70 border border-rose-500/40 text-rose-300 font-bold text-sm transition flex items-center space-x-2"
              >
                <Flame className="w-4 h-4" />
                <span>Live Attack Console</span>
              </button>
              <button
                onClick={() => onNavigate('pipeline')}
                className="px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 font-bold text-sm transition flex items-center space-x-2"
              >
                <Radio className="w-4 h-4 text-cyan-400" />
                <span>Pipeline Telemetry</span>
              </button>
            </div>
          </div>

          {/* Stat Pills */}
          <div className="grid grid-cols-2 gap-3 shrink-0">
            <div className="p-4 rounded-2xl bg-slate-900/80 border border-cyan-500/20 text-center">
              <p className="text-2xl font-extrabold text-cyan-300 font-mono">{loading ? '–' : agents.length}</p>
              <p className="text-[10px] font-mono uppercase text-slate-400 mt-0.5">Agents Indexed</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-900/80 border border-indigo-500/20 text-center">
              <p className="text-2xl font-extrabold text-indigo-300 font-mono">{loading ? '–' : scenarios.length}</p>
              <p className="text-[10px] font-mono uppercase text-slate-400 mt-0.5">Scenarios Library</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-900/80 border border-emerald-500/20 text-center">
              <p className="text-2xl font-extrabold text-emerald-300 font-mono">{loading ? '–' : validatedScenarios.length}</p>
              <p className="text-[10px] font-mono uppercase text-slate-400 mt-0.5">Validated Tests</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-900/80 border border-amber-500/20 text-center">
              <p className="text-2xl font-extrabold text-amber-300 font-mono">
                {loading || !calibration ? '–' : `${(calibration.agreement_rate > 1 ? calibration.agreement_rate : calibration.agreement_rate * 100).toFixed(2)}%`}
              </p>
              <p className="text-[10px] font-mono uppercase text-slate-400 mt-0.5">Judge Agreement</p>
            </div>
          </div>
        </div>
      </div>

      {/* 6-Engine Pipeline Flow */}
      <div>
        <h2 className="text-lg font-extrabold text-slate-100 mb-4">
          Six-Engine Evaluation Pipeline
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {engineSteps.map((step, idx) => {
            const Icon = step.icon;
            return (
              <div
                key={step.id}
                onClick={() => onNavigate(step.page)}
                className="group p-5 rounded-2xl glass-card border border-slate-800 hover:border-slate-700 cursor-pointer transition-all hover:shadow-lg hover:-translate-y-0.5"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className={`p-2.5 rounded-xl bg-gradient-to-br ${step.color} bg-opacity-20 border border-white/10`}>
                    <Icon className="w-4 h-4 text-white" />
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 border border-slate-800 px-1.5 py-0.5 rounded">
                    #{idx + 1}
                  </span>
                </div>
                <h3 className="text-sm font-bold text-slate-100 mb-1">{step.label}</h3>
                <p className="text-[11px] text-slate-400 leading-relaxed">{step.description}</p>
                <div className="mt-3 flex items-center space-x-1 text-[11px] font-semibold text-cyan-400 group-hover:text-cyan-300 transition">
                  <span>Open Module</span>
                  <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent Agents Table */}
      {!loading && agents.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-slate-100">Registered Agents</h2>
            <button
              onClick={() => onNavigate('agents')}
              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1 font-semibold"
            >
              <span>View All & X-Ray</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          <div className="rounded-2xl overflow-hidden border border-slate-800">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-900/80 border-b border-slate-800">
                  <th className="text-left px-4 py-3 font-mono text-slate-400 uppercase text-[10px]">Agent Name</th>
                  <th className="text-left px-4 py-3 font-mono text-slate-400 uppercase text-[10px]">Domain</th>
                  <th className="text-left px-4 py-3 font-mono text-slate-400 uppercase text-[10px]">Version</th>
                  <th className="text-left px-4 py-3 font-mono text-slate-400 uppercase text-[10px]">Tools</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((a, i) => (
                  <tr
                    key={a.id}
                    onClick={() => onNavigate('agents')}
                    className={`border-b border-slate-800/80 cursor-pointer hover:bg-slate-900/40 transition ${i % 2 === 0 ? 'bg-slate-950' : 'bg-slate-900/20'}`}
                  >
                    <td className="px-4 py-2.5">
                      <span className="font-bold text-slate-100">{a.name}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-slate-400 font-mono">{a.domain}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-500/30 font-mono text-[10px]">
                        {a.version_label}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-slate-300">{a.tools.length} tools</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
