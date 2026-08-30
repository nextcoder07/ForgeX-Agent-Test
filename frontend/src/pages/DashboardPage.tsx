import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from "react-router-dom";
import { fetchAgents, fetchScenarioLibrary, fetchCalibrationReport, startFullEvaluationPipeline } from '../api/client';
import type { AgentRecord, Scenario, CalibrationReport } from '../api/client';
import { Activity, ShieldCheck, Layers, Cpu, Flame, ArrowRight, Sparkles, GitCompare, CheckCircle2, TrendingUp, RefreshCw, Radio, Wrench, Zap } from 'lucide-react';
import type { PageId } from '../components/Navbar';

interface DashboardPageProps {
}

export const DashboardPage: React.FC<DashboardPageProps> = ({}) => {
  const navigate = useNavigate();
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [calibration, setCalibration] = useState<CalibrationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [startingPipeline, setStartingPipeline] = useState(false);
  const [pipelineMessage, setPipelineMessage] = useState('');

  useEffect(() => {
    Promise.allSettled([
      fetchAgents().then(setAgents),
      fetchScenarioLibrary().then(setScenarios),
      fetchCalibrationReport().then(setCalibration),
    ]).finally(() => setLoading(false));
  }, []);

  const categories = [...new Set(scenarios.map(s => s.category))];
  const validatedScenarios = scenarios.filter(s => s.validation_status === 'VALIDATED');

  const handleStartFullPipeline = async () => {
    const agent = agents[0];
    if (!agent) {
      navigate('/intake');
      return;
    }
    setStartingPipeline(true);
    setPipelineMessage('');
    try {
      const run = await startFullEvaluationPipeline(agent.id, 'simulation');
      localStorage.setItem('lastPipelineRunId', run.id);
      setPipelineMessage(`Pipeline started for ${agent.display_name || agent.name}.`);
      navigate('/pipeline');
    } catch (error) {
      setPipelineMessage(error instanceof Error ? error.message : 'Unable to start pipeline.');
    } finally {
      setStartingPipeline(false);
    }
  };

  const engineSteps = [
    { id: 'intake', label: '1. Agent Intake & AST Reconstruction', description: 'Upload or select any agent. AST static analysis + Gemini spec reconstruction maps tools, goals, and prompt-code discrepancies.', icon: Sparkles, color: 'from-cyan-500 to-cyan-700', page: 'intake' as PageId },
    { id: 'scenarios', label: '2. Scenario Intelligence Engine', description: 'Auto-generates 8-category adversarial + normal test suites. Critic validates each scenario before entering the library.', icon: Layers, color: 'from-indigo-500 to-indigo-700', page: 'scenarios' as PageId },
    { id: 'dependencies', label: '3. Dependency & Tool Gateway', description: 'Configures environment variables, API key resolution, mock fallbacks, and sandbox tool permissions.', icon: ShieldCheck, color: 'from-blue-500 to-blue-700', page: 'dependencies' as PageId },
    { id: 'executions', label: '4. Sandboxed Execution Engine', description: 'Runs agents in ephemeral sandboxes with chaos fault injection (latency, 500 errors, rate limits) and trace collection.', icon: Radio, color: 'from-violet-500 to-violet-700', page: 'executions' as PageId },
    { id: 'evaluations', label: '5. Hybrid Evaluation & 2D Scorecard', description: 'Dual-tier grading (deterministic rules + calibrated Gemini judge). Computes 2D Safety x Capability matrix & failure clusters.', icon: Zap, color: 'from-amber-500 to-amber-700', page: 'evaluations' as PageId },
    { id: 'fix-agent', label: '6. Automated Remediation & Self-Healing', description: 'Synthesizes AST code patches and hardened prompts to fix identified failure clusters with 1-click verification.', icon: Wrench, color: 'from-rose-500 to-rose-700', page: 'fix-agent' as PageId },
  ];

  const auxiliaryModules = [
    { id: 'live-attack', label: 'Live Red-Teaming Attack Console', description: 'Fire real-time adversarial prompts. Instant counterfactual replay compares agent response against clean control to prove causation.', icon: Flame, color: 'from-rose-500 to-rose-700', page: 'live-attack' as PageId },
    { id: 'failures', label: 'Failure Clustering & Root-Cause Analysis', description: 'ML clustering groups similar failures into actionable root-cause clusters with remediation recommendations.', icon: Activity, color: 'from-amber-500 to-amber-700', page: 'failures' as PageId },
    { id: 'scorecard', label: 'Regression & Version Diff', description: 'Compare two agent versions with safety/capability delta. Detect regressions before deploying updates.', icon: GitCompare, color: 'from-emerald-500 to-emerald-700', page: 'scorecard' as PageId },
    { id: 'calibration', label: 'LLM Judge Calibration Benchmark', description: 'Benchmark AI judge verdicts against human gold-standard labels to ensure agreement rate and low error rates.', icon: CheckCircle2, color: 'from-cyan-500 to-cyan-700', page: 'calibration' as PageId },
  ];

  return (
    <div className="space-y-5 sm:space-y-6 max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl p-4 sm:p-6 border border-slate-700/80 bg-gradient-to-br from-slate-950 via-indigo-950/50 to-slate-950 shadow-xl">
        {/* Glowing BG */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-2 left-1/3 w-60 h-60 bg-cyan-600/10 rounded-full blur-3xl" />
          <div className="absolute bottom-2 right-1/4 w-48 h-48 bg-indigo-600/10 rounded-full blur-3xl" />
        </div>

        <div className="relative z-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-5">
          <div className="space-y-2.5">
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 text-[9px] sm:text-[10px] font-mono uppercase rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 tracking-wider">
                AI Reliability CI Platform
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl lg:text-3xl font-extrabold text-white leading-tight">
              Agent Evaluation &<br />
              <span className="bg-gradient-to-r from-cyan-300 via-indigo-300 to-rose-300 bg-clip-text text-transparent">
                Reliability Engine
              </span>
            </h1>
            <p className="text-slate-300 text-xs sm:text-sm max-w-xl leading-relaxed">
              Autonomous AI agents fail on ~70% of real-world tasks. Continuous integration automatically generates adversarial test suites, runs sandboxed evaluations, proves failure causation, and produces reliability scorecards before deployment.
            </p>

            <div className="flex items-center space-x-2 pt-1 flex-wrap gap-2">
              <button
                onClick={() => navigate("/intake")}
                className="px-3.5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 via-indigo-600 to-rose-600 hover:from-cyan-400 hover:to-rose-500 text-white font-bold text-xs sm:text-sm shadow-md shadow-cyan-500/20 flex items-center space-x-1.5 transition"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Bring Your Agent</span>
              </button>
              <button
                onClick={() => navigate("/live-attack")}
                className="px-3.5 py-2 rounded-lg bg-slate-900/90 border border-slate-700 text-slate-400 font-bold text-xs sm:text-sm transition flex items-center space-x-1.5 cursor-pointer"
              >
                <Flame className="w-3.5 h-3.5 text-slate-500" />
                <span>Live Attack (Disabled)</span>
              </button>
              <button
                onClick={() => navigate("/pipeline")}
                className="px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-bold text-xs sm:text-sm transition flex items-center space-x-1.5"
              >
                <Radio className="w-3.5 h-3.5 text-cyan-400" />
                <span>Pipeline Telemetry</span>
              </button>
              <button
                onClick={handleStartFullPipeline}
                disabled={startingPipeline}
                className="px-3.5 py-2 rounded-lg bg-emerald-950/70 hover:bg-emerald-900/80 border border-emerald-500/50 text-emerald-200 font-bold text-xs sm:text-sm transition flex items-center space-x-1.5 disabled:opacity-50"
              >
                <Zap className={`w-3.5 h-3.5 ${startingPipeline ? 'animate-pulse' : ''}`} />
                <span>{startingPipeline ? 'Starting Pipeline...' : 'Run Full Lifecycle'}</span>
              </button>
            </div>
            {pipelineMessage && <p className="text-xs text-amber-300 pt-1">{pipelineMessage}</p>}
          </div>

          {/* Stat Pills */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 gap-2.5 w-full lg:w-auto shrink-0">
            <div className="p-3 rounded-xl bg-slate-900/90 border border-cyan-500/30 text-center">
              <p className="text-xl sm:text-2xl font-extrabold text-cyan-300 font-mono">{loading ? '–' : agents.length}</p>
              <p className="text-[9px] sm:text-[10px] font-mono uppercase text-slate-300 mt-0.5">Agents Indexed</p>
            </div>
            <div className="p-3 rounded-xl bg-slate-900/90 border border-indigo-500/30 text-center">
              <p className="text-xl sm:text-2xl font-extrabold text-indigo-300 font-mono">{loading ? '–' : scenarios.length}</p>
              <p className="text-[9px] sm:text-[10px] font-mono uppercase text-slate-300 mt-0.5">Scenarios Designed</p>
            </div>
            <div className="p-3 rounded-xl bg-slate-900/90 border border-emerald-500/30 text-center">
              <p className="text-xl sm:text-2xl font-extrabold text-emerald-300 font-mono">{loading ? '–' : validatedScenarios.length}</p>
              <p className="text-[9px] sm:text-[10px] font-mono uppercase text-slate-300 mt-0.5">Spec-Validated</p>
            </div>
            <div className="p-3 rounded-xl bg-slate-900/90 border border-amber-500/30 text-center">
              <p className="text-xl sm:text-2xl font-extrabold text-amber-300 font-mono">
                {loading || !calibration ? '–' : `${(calibration.agreement_rate > 1 ? calibration.agreement_rate : calibration.agreement_rate * 100).toFixed(1)}%`}
              </p>
              <p className="text-[9px] sm:text-[10px] font-mono uppercase text-slate-300 mt-0.5">Judge Agreement</p>
            </div>
          </div>
        </div>
      </div>

      {/* 6-Engine Pipeline Flow */}
      <div>
        <h2 className="text-base sm:text-lg font-extrabold text-slate-100 mb-3 flex items-center justify-between">
          <span>Six-Engine Evaluation Pipeline</span>
          <span className="text-xs font-mono font-semibold text-cyan-400">1 → 2 → 3 → 4 → 5 → 6</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {engineSteps.map((step, idx) => {
            const Icon = step.icon;
            return (
              <div
                key={step.id}
                onClick={() => navigate(`/${step.page}`)}
                className="group p-3.5 sm:p-4 rounded-xl glass-card border border-slate-700/70 hover:border-cyan-500/50 cursor-pointer transition-all hover:shadow-md hover:-translate-y-0.5"
              >
                <div className="flex items-start justify-between mb-2.5">
                  <div className={`p-2 rounded-lg bg-gradient-to-br ${step.color} bg-opacity-30 border border-white/10`}>
                    <Icon className="w-4 h-4 text-white" />
                  </div>
                  <span className="text-[10px] font-mono text-cyan-300 border border-cyan-500/40 bg-cyan-950/60 px-1.5 py-0.5 rounded font-bold">
                    Engine #{idx + 1}
                  </span>
                </div>
                <h3 className="text-xs sm:text-sm font-bold text-slate-100 mb-1">{step.label}</h3>
                <p className="text-[11px] sm:text-xs text-slate-300 leading-relaxed">{step.description}</p>
                <div className="mt-2.5 flex items-center space-x-1 text-[11px] font-semibold text-cyan-400 group-hover:text-cyan-300 transition">
                  <span>Open Module</span>
                  <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Auxiliary Analysis Modules */}
      <div>
        <h2 className="text-base sm:text-lg font-extrabold text-slate-100 mb-3">
          Specialized Analysis & Telemetry Tools
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {auxiliaryModules.map((step) => {
            const Icon = step.icon;
            return (
              <div
                key={step.id}
                onClick={() => navigate(`/${step.page}`)}
                className="group p-3 sm:p-3.5 rounded-xl glass-card border border-slate-700/60 hover:border-indigo-500/50 cursor-pointer transition-all hover:shadow-md hover:-translate-y-0.5 space-y-2"
              >
                <div className="flex items-center space-x-2">
                  <div className={`p-1.5 rounded-md bg-gradient-to-br ${step.color} bg-opacity-30 border border-white/10`}>
                    <Icon className="w-3.5 h-3.5 text-white" />
                  </div>
                  <h3 className="text-xs font-bold text-slate-100 truncate">{step.label}</h3>
                </div>
                <p className="text-[11px] text-slate-300 leading-relaxed line-clamp-3">{step.description}</p>
                <div className="flex items-center space-x-1 text-[10px] font-semibold text-indigo-400 group-hover:text-indigo-300 transition">
                  <span>Launch Tool</span>
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
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm sm:text-base font-bold text-slate-100">Registered Agents</h2>
            <button
              onClick={() => navigate("/agents")}
              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1 font-semibold"
            >
              <span>View All & X-Ray</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          <div className="rounded-xl overflow-hidden border border-slate-700/80 responsive-table-container">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-900/90 border-b border-slate-700/80">
                  <th className="text-left px-3.5 py-2.5 font-mono text-slate-300 uppercase text-[10px]">Agent Name</th>
                  <th className="text-left px-3.5 py-2.5 font-mono text-slate-300 uppercase text-[10px]">Domain</th>
                  <th className="text-left px-3.5 py-2.5 font-mono text-slate-300 uppercase text-[10px]">Version</th>
                  <th className="text-left px-3.5 py-2.5 font-mono text-slate-300 uppercase text-[10px]">Tools</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((a, i) => (
                  <tr
                    key={a.id}
                    onClick={() => navigate("/agents")}
                    className={`border-b border-slate-800 cursor-pointer hover:bg-slate-900/60 transition ${i % 2 === 0 ? 'bg-slate-950' : 'bg-slate-900/40'}`}
                  >
                    <td className="px-3.5 py-2">
                      <span className="font-bold text-slate-100">{a.name}</span>
                    </td>
                    <td className="px-3.5 py-2">
                      <span className="text-slate-300 font-mono">{a.domain}</span>
                    </td>
                    <td className="px-3.5 py-2">
                      <span className="px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-500/40 font-mono text-[10px]">
                        {a.version_label}
                      </span>
                    </td>
                    <td className="px-3.5 py-2">
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
