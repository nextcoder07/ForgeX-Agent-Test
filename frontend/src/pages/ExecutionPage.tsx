import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from "react-router-dom";
import {
  Cpu,
  Layers,
  CheckSquare,
  Square,
  Play,
  CheckCircle,
  AlertTriangle,
  Zap,
  ArrowRight,
  Shield,
  Clock,
  Activity,
  ChevronRight,
  CheckCircle2,
} from 'lucide-react';
import type { PageId } from '../components/Navbar';
import type { AgentRecord, Scenario, ExecutionJob } from '../api/client';
import {
  fetchAgents,
  fetchScenarioLibrary,
  runExecutionJob,
  fetchExecutionJobDetails,
  evaluateExecutionJob,
} from '../api/client';
import { LiveProcessMonitor } from '../components/LiveProcessMonitor';

interface ExecutionPageProps {
  onExecutionEvaluated?: (evalJob: any) => void; // Callback to pass eval job results to evaluation page
}

export const ExecutionPage: React.FC<ExecutionPageProps> = ({ onExecutionEvaluated }) => {
  const navigate = useNavigate();
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([]);
  
  // Job Status
  const [executionJob, setExecutionJob] = useState<ExecutionJob | null>(null);
  const [running, setRunning] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [loadingScenarios, setLoadingScenarios] = useState(false);

  const pollIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    // Load agents
    fetchAgents().then(list => {
      setAgents(list);
      if (list.length > 0) {
        setSelectedAgentId(list[0].id);
      }
    });
  }, []);

  // Fetch scenarios whenever selected agent changes
  useEffect(() => {
    if (!selectedAgentId) return;
    setLoadingScenarios(true);
    fetchScenarioLibrary(selectedAgentId)
      .then(list => {
        setScenarios(list);
        setSelectedScenarioIds(list.map(s => s.id)); // Auto-select all by default
      })
      .catch(e => console.error('Failed to fetch scenarios:', e))
      .finally(() => setLoadingScenarios(false));
  }, [selectedAgentId]);

  const handleSelectAll = () => {
    if (selectedScenarioIds.length === scenarios.length) {
      setSelectedScenarioIds([]);
    } else {
      setSelectedScenarioIds(scenarios.map(s => s.id));
    }
  };

  const handleToggleScenario = (id: string) => {
    setSelectedScenarioIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleStartExecution = async () => {
    if (selectedScenarioIds.length === 0) return;
    setRunning(true);
    setExecutionJob(null);

    try {
      const job = await runExecutionJob(selectedAgentId, selectedScenarioIds, true);
      setExecutionJob(job);

      // Start polling
      pollIntervalRef.current = window.setInterval(async () => {
        try {
          const updatedJob = await fetchExecutionJobDetails(job.id);
          setExecutionJob(updatedJob);
          if (updatedJob.status === 'completed' || updatedJob.status === 'failed') {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setRunning(false);
          }
        } catch (e) {
          console.error('Error polling execution job:', e);
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setRunning(false);
        }
      }, 1500);

    } catch (e) {
      console.error('Failed to run execution:', e);
      setRunning(false);
    }
  };

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  const handleSendToEvaluation = async () => {
    if (!executionJob || executionJob.status !== 'completed') return;
    setEvaluating(true);
    try {
      // POST /api/evaluations/evaluate-execution with execution_job_id
      const evalJob = await evaluateExecutionJob(executionJob.id);
      // Pass full evalJob to App.tsx which sets activeEvaluationJobId then navigates
      if (onExecutionEvaluated) {
        onExecutionEvaluated(evalJob);
      }
      // App.tsx now handles navigation to 'evaluations' with the correct job ID
    } catch (e) {
      console.error('[SEND_TO_EVAL] Failed to trigger evaluation:', e);
      // Don't navigate if evaluation creation failed
    } finally {
      setEvaluating(false);
    }
  };



  const selectedAgent = agents.find(a => a.id === selectedAgentId);
  const progressPct = executionJob && executionJob.total_scenarios > 0
    ? Math.round((executionJob.completed_scenarios / executionJob.total_scenarios) * 100)
    : 0;

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
          <Cpu className="w-6 h-6 text-indigo-400" />
          <span>Sandbox Execution Console</span>
        </h1>
        <p className="text-sm text-slate-400">
          Run your registered agent against target scenario batches inside the sandboxed environment to collect raw execution traces.
        </p>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Side: Agent Selection & Config */}
        <div className="lg:col-span-1 space-y-6">
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/80 space-y-4">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400">
              1. Choose Target Agent
            </h2>
            
            <div className="space-y-2">
              <label className="text-xs text-slate-500 block">Active Target</label>
              <select
                value={selectedAgentId}
                onChange={e => setSelectedAgentId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition-colors"
                disabled={running}
              >
                {agents.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.display_name || a.name}
                  </option>
                ))}
              </select>
            </div>

            {selectedAgent && (
              <div className="space-y-4 pt-2">
                <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2 text-xs">
                  <p className="text-slate-400">
                    <span className="text-slate-500 font-mono block">AGENT ID</span>
                    <span className="font-mono">{selectedAgent.id}</span>
                  </p>
                  <p className="text-slate-400">
                    <span className="text-slate-500 font-mono block">DOMAIN</span>
                    <span className="uppercase font-semibold text-indigo-400">{selectedAgent.domain}</span>
                  </p>
                  <p className="text-slate-400">
                    <span className="text-slate-500 font-mono block">VERSION</span>
                    <span>{selectedAgent.version_label || 'v1.0'}</span>
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-xs text-slate-500 block">System Prompt configuration</label>
                  <textarea
                    readOnly
                    value={selectedAgent.system_prompt}
                    className="w-full h-40 bg-slate-950 border border-slate-900 rounded-xl p-3 text-[11px] font-mono text-slate-300 resize-none focus:outline-none"
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Scenario List & Execution */}
        <div className="lg:col-span-2 space-y-6">
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/80 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                2. Select Scenarios ({selectedScenarioIds.length}/{scenarios.length})
              </h2>
              {scenarios.length > 0 && (
                <button
                  onClick={handleSelectAll}
                  disabled={running}
                  className="px-3 py-1 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono hover:text-slate-200 transition disabled:opacity-50"
                >
                  {selectedScenarioIds.length === scenarios.length ? 'DESELECT ALL' : 'SELECT ALL'}
                </button>
              )}
            </div>

            {loadingScenarios ? (
              <div className="py-12 text-center text-slate-500 text-xs font-mono">
                Loading scenario library...
              </div>
            ) : scenarios.length === 0 ? (
              <div className="py-12 text-center text-slate-500 text-xs font-mono space-y-2">
                <p>No scenarios found for this agent.</p>
                <button
                  onClick={() => navigate("/scenarios")}
                  className="text-indigo-400 hover:underline"
                >
                  Generate scenarios now →
                </button>
              </div>
            ) : (
              <div className="max-h-72 overflow-y-auto space-y-2 pr-1">
                {scenarios.map(sc => {
                  const isChecked = selectedScenarioIds.includes(sc.id);
                  return (
                    <div
                      key={sc.id}
                      onClick={() => !running && handleToggleScenario(sc.id)}
                      className={`p-3.5 rounded-xl border flex items-center justify-between transition cursor-pointer select-none ${
                        isChecked
                          ? 'bg-indigo-950/20 border-indigo-500/30'
                          : 'bg-slate-950 border-slate-900 hover:border-slate-800'
                      }`}
                    >
                      <div className="flex items-center space-x-3 min-w-0">
                        {isChecked ? (
                          <CheckCircle2 className="w-4 h-4 text-indigo-400 shrink-0" />
                        ) : (
                          <div className="w-4 h-4 rounded-full border border-slate-700 shrink-0" />
                        )}
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-slate-200 truncate">{sc.title}</p>
                          <p className="text-[10px] text-slate-500 truncate font-mono mt-0.5">
                            Category: <span className="uppercase text-slate-400">{sc.category}</span> · Required: {sc.required_capabilities.join(', ')}
                          </p>
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-slate-700" />
                    </div>
                  );
                })}
              </div>
            )}

            {/* Launch controls */}
            {scenarios.length > 0 && (
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                <p className="text-[10px] text-slate-500 font-mono">
                  Sandbox executions will run in the background.
                </p>
                <button
                  onClick={handleStartExecution}
                  disabled={running || selectedScenarioIds.length === 0}
                  className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-extrabold text-xs shadow-lg shadow-indigo-500/20 flex items-center space-x-2 transition disabled:opacity-50 disabled:scale-100 active:scale-95"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Execute {selectedScenarioIds.length} Scenarios</span>
                </button>
              </div>
            )}
          </div>

          {/* Execution Progress Panel */}
          {executionJob && (
            <div className="p-5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/80 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Clock className="w-4 h-4 text-indigo-400" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                    Execution Job: {executionJob.id}
                  </h3>
                </div>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
                  executionJob.status === 'completed'
                    ? 'bg-emerald-950 text-emerald-400 border-emerald-500/30'
                    : executionJob.status === 'running'
                    ? 'bg-indigo-950 text-indigo-400 border-indigo-500/30 animate-pulse'
                    : 'bg-slate-900 text-slate-400 border-slate-800'
                }`}>
                  {executionJob.status}
                </span>
              </div>

              {/* Progress Bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-[11px] font-mono">
                  <span className="text-slate-400">Sandbox Runs</span>
                  <span className="text-slate-200">
                    {executionJob.completed_scenarios}/{executionJob.total_scenarios} ({progressPct}%)
                  </span>
                </div>
                <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-300"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              </div>

              {/* Proceed to evaluation */}
              {executionJob.status === 'completed' && (
                <div className="p-4 rounded-xl bg-indigo-950/10 border border-indigo-500/20 flex items-center justify-between flex-wrap gap-4 animate-fade-in">
                  <div>
                    <h4 className="text-xs font-bold text-indigo-300 flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 fill-current text-indigo-400" />
                      Sandbox Traces Saved
                    </h4>
                    <p className="text-[10px] text-slate-400 mt-1">
                      Ready to judge sandbox traces using hybrid LLM evaluation.
                    </p>
                  </div>
                  <button
                    onClick={handleSendToEvaluation}
                    disabled={evaluating}
                    className="px-5 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-600 hover:from-emerald-400 hover:to-cyan-500 disabled:from-slate-700 disabled:to-slate-700 text-white font-extrabold text-[11px] shadow-lg shadow-emerald-500/25 flex items-center space-x-1.5 transition"
                  >
                    <span>
                      {evaluating ? '[ Creating Evaluation Job... ]' : '[ Send to Evaluation Engine ]'}
                    </span>
                    {!evaluating && <ArrowRight className="w-3.5 h-3.5" />}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Process activity log */}
      <LiveProcessMonitor />

    </div>
  );
};
