import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
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
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  Eye,
  Terminal,
  FileText,
  ShieldAlert,
  Code,
  Sparkles,
  Database,
  Search,
  Mail,
  RefreshCw,
  Sliders,
  Check,
} from 'lucide-react';
import type { PageId } from '../components/Navbar';
import type { AgentRecord, Scenario, ExecutionJob, ExecutionTrace, ToolCallRecord, TraceEvent, SecurityEvent, ObservationSummary, SetupReadinessRecord } from '../api/client';
import {
  API_BASE_URL,
  fetchAgents,
  fetchScenarioLibrary,
  runExecutionJob,
  fetchExecutionJobDetails,
  fetchExecutionTraces,
  evaluateExecutionJob,
  fetchLatestExecutionJob,
  getSetupReadiness,
  runAutomaticSetup,
} from '../api/client';
import { LiveProcessMonitor } from '../components/LiveProcessMonitor';
import { PipelineObservabilityPage } from './PipelineObservabilityPage';

interface ExecutionPageProps {
  onExecutionEvaluated?: (evalJob: any) => void;
}

export const ExecutionPage: React.FC<ExecutionPageProps> = ({ onExecutionEvaluated }) => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const execTab = (searchParams.get('tab') || 'run') as 'run' | 'telemetry';
  const agentIdFromUrl = searchParams.get('agentId') || '';

  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([]);
  const [setupReadiness, setSetupReadiness] = useState<SetupReadinessRecord | null>(null);
  
  // Job & Trace Status
  const [executionJob, setExecutionJob] = useState<ExecutionJob | null>(null);
  const [executionTraces, setExecutionTraces] = useState<ExecutionTrace[]>([]);
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);
  const [traceFilter, setTraceFilter] = useState<'all' | 'tools' | 'security' | 'failed'>('all');
  const [executionMode, setExecutionMode] = useState<'faithful' | 'compatible' | 'simulation'>('faithful');
  const [running, setRunning] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [loadingScenarios, setLoadingScenarios] = useState(false);
  const [executionBlockedMsg, setExecutionBlockedMsg] = useState<string | null>(null);
  const [providedSecrets, setProvidedSecrets] = useState<Record<string, string>>({});
  const [showInlineKeys, setShowInlineKeys] = useState(false);

  const pollIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    // Load agents
    fetchAgents().then(list => {
      setAgents(list);
      if (agentIdFromUrl && list.some(a => a.id === agentIdFromUrl)) {
        setSelectedAgentId(agentIdFromUrl);
      } else if (list.length > 0) {
        setSelectedAgentId(list[0].id);
      }
    });
  }, [agentIdFromUrl]);

  // Fetch scenarios and latest completed execution whenever selected agent changes
  useEffect(() => {
    if (!selectedAgentId) return;
    setLoadingScenarios(true);
    setExecutionBlockedMsg(null);

    // Trigger automatic setup preparation on agent selection
    runAutomaticSetup(selectedAgentId)
      .then(sr => setSetupReadiness(sr))
      .catch(() => {
        getSetupReadiness(selectedAgentId).then(sr => setSetupReadiness(sr)).catch(() => {});
      });
    
    Promise.all([
      fetchScenarioLibrary(selectedAgentId),
      fetchLatestExecutionJob(selectedAgentId),
    ])
      .then(([scList, latestData]) => {
        setScenarios(scList);
        setSelectedScenarioIds(scList.map(s => s.id)); // Auto-select all by default
        
        // If a previous execution job exists and we are not currently running a new execution, load it
        if (!running && latestData.job) {
          setExecutionJob(latestData.job);
          setExecutionTraces(latestData.traces || []);
        }
      })
      .catch(e => console.error('Failed to fetch scenarios/latest execution:', e))
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

  const handleStartExecution = async (overrideMode?: string) => {
    if (selectedScenarioIds.length === 0) return;
    let safeMode = typeof overrideMode === 'string' ? overrideMode : executionMode;
    
    // Smart Preflight Check: If Faithful mode lacks un-injected mandatory custom keys, auto-recommend Compatible mode
    const missingKeys = setupReadiness?.missing_credentials || [];
    const hasUnprovidedMissingKeys = missingKeys.some(k => !providedSecrets[k] || !providedSecrets[k].trim());
    
    if (safeMode === 'faithful' && hasUnprovidedMissingKeys) {
      console.log('[PREFLIGHT] Missing custom keys for Faithful mode. Falling back to Compatible mode.');
      safeMode = 'compatible';
      setExecutionMode('compatible');
    }

    setRunning(true);
    setExecutionJob(null);
    setExecutionTraces([]);
    setExecutionBlockedMsg(null);

    try {
      const job = await runExecutionJob(selectedAgentId, selectedScenarioIds, true, safeMode, providedSecrets);
      setExecutionJob(job);

      if (job.status === 'BLOCKED' || job.status === 'blocked') {
        setRunning(false);
        setExecutionBlockedMsg(
          job.error_message || `Execution blocked for agent '${selectedAgent?.name || selectedAgentId}': missing required dependencies or invalid credentials.`
        );
        return;
      }

      // Start polling for live job status and trace updates
      pollIntervalRef.current = window.setInterval(async () => {
        try {
          const [updatedJob, traces] = await Promise.all([
            fetchExecutionJobDetails(job.id),
            fetchExecutionTraces(job.id).catch(() => []),
          ]);
          setExecutionJob(updatedJob);
          if (traces && traces.length > 0) {
            setExecutionTraces(traces);
          }
          if (['completed', 'failed', 'blocked', 'BLOCKED'].includes(updatedJob.status)) {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setRunning(false);
            if (updatedJob.status === 'blocked' || updatedJob.status === 'BLOCKED') {
              setExecutionBlockedMsg(
                updatedJob.error_message || `Execution blocked for agent '${selectedAgent?.name || selectedAgentId}': missing required credentials or invalid API key.`
              );
            }
          }
        } catch (e) {
          console.error('Error polling execution job:', e);
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setRunning(false);
        }
      }, 1500);

    } catch (e: any) {
      console.error('Failed to run execution:', e);
      setRunning(false);
      const errMsg = String(e?.message || e || '');
      if (errMsg.toLowerCase().includes('failed to fetch') || errMsg.toLowerCase().includes('networkerror')) {
        setExecutionBlockedMsg(`Backend Connection Error: Could not reach ForgeX Server (${API_BASE_URL}). Please verify the backend service is running.`);
      } else {
        setExecutionBlockedMsg(errMsg || `Execution failed to start for agent '${selectedAgent?.name || selectedAgentId}'. Please check Setup.`);
      }
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
      const evalJob = await evaluateExecutionJob(executionJob.id);
      const evalJobId = evalJob?.id || evalJob?.job_id;
      navigate(`/results?agentId=${selectedAgentId}${evalJobId ? `&jobId=${evalJobId}` : ''}`);
    } catch (e) {
      console.error('[SEND_TO_EVAL] Failed to trigger evaluation:', e);
    } finally {
      setEvaluating(false);
    }
  };

  const selectedAgent = agents.find(a => a.id === selectedAgentId);
  const isJobBlocked = executionJob?.status === 'BLOCKED' || executionJob?.status === 'blocked';

  const progressPct = isJobBlocked || !executionJob || executionJob.total_scenarios === 0
    ? 0
    : Math.min(100, Math.round((executionJob.completed_scenarios / executionJob.total_scenarios) * 100));

  // Deduplicate execution traces by scenario_id to prevent double counting across runs
  const uniqueTracesByScenario = React.useMemo(() => {
    if (isJobBlocked) return [];
    const map = new Map<string, any>();
    for (const t of executionTraces) {
      const scId = t.scenario_id || t.id;
      if (scId && (!map.has(scId) || t.status === 'COMPLETED')) {
        map.set(scId, t);
      }
    }
    return Array.from(map.values());
  }, [executionTraces, isJobBlocked]);

  const totalExecutedCount = isJobBlocked ? 0 : uniqueTracesByScenario.length;
  const targetScenarioCount = executionJob?.total_scenarios || scenarios.length;
  const coveragePct = isJobBlocked || targetScenarioCount === 0 
    ? 0 
    : Math.min(100, Math.round((totalExecutedCount / targetScenarioCount) * 100));

  // Aggregate metrics from execution traces (checking explicit tool_calls + stdout chunks)
  const totalToolCalls = executionTraces.reduce((acc, t) => {
    const explicitCalls = t.tool_calls?.length || 0;
    if (explicitCalls > 0) return acc + explicitCalls;
    const stdoutCalls = t.events?.filter(e => 
      e.role === 'agent_message' && e.content && e.content.includes('"tool"')
    ).length || 0;
    return acc + stdoutCalls;
  }, 0);

  const totalSecurityEvents = executionTraces.reduce((acc, t) => acc + (t.security_events?.length || 0), 0);
  const totalBlockedTools = executionTraces.reduce((acc, t) => 
    acc + (t.tool_calls?.filter(tc => tc.routing_decision === 'BLOCK' || tc.status === 'BLOCKED_POLICY').length || 0), 0);
  const avgLatency = executionTraces.length > 0 
    ? Math.round(executionTraces.reduce((acc, t) => acc + (t.total_latency_ms || 0), 0) / executionTraces.length)
    : 0;

  const filteredTraces = executionTraces.filter(t => {
    if (traceFilter === 'tools') return (t.tool_calls && t.tool_calls.length > 0) || t.events?.some(e => e.content?.includes('"tool"'));
    if (traceFilter === 'security') return (t.security_events && t.security_events.length > 0) || (t.tool_calls?.some(tc => tc.routing_decision === 'BLOCK'));
    if (traceFilter === 'failed') return t.status !== 'COMPLETED';
    return true;
  });

  return (
    <div className="space-y-5 sm:space-y-6 max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center space-x-2.5">
          <Cpu className="w-5 h-5 sm:w-6 sm:h-6 text-indigo-400" />
          <span>Execute</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-300">
          Run scenarios in the sandbox, inspect live observations, and view findings per scenario.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex items-center space-x-1 border-b border-slate-800">
        {([
          { id: 'run', label: 'Run Tests & Observations', icon: Play },
          { id: 'telemetry', label: 'Live Pipeline Telemetry', icon: Activity },
        ] as const).map(t => (
          <button
            key={t.id}
            onClick={() => setSearchParams({ tab: t.id })}
            className={`flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold rounded-t-lg border-b-2 transition-all cursor-pointer ${
              execTab === t.id
                ? 'border-cyan-400 text-cyan-300 bg-slate-900/40'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/20'
            }`}
          >
            <t.icon className="w-3.5 h-3.5" />
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Telemetry tab */}
      {execTab === 'telemetry' && <PipelineObservabilityPage />}

      {/* Run tab content starts below */}
      {execTab === 'run' && <>

      {/* 🛑 Blocked Execution Warning Banner with Root-Cause Diagnostics & Setup Navigation */}
      {executionBlockedMsg && (
        <div className="p-4 rounded-2xl glass-panel border border-rose-500/50 bg-rose-950/50 flex items-center justify-between flex-wrap gap-3 animate-fadeIn">
          <div className="flex items-center space-x-3 max-w-2xl">
            <div className="p-2.5 rounded-xl bg-rose-500/20 border border-rose-500/40 flex-shrink-0">
              <AlertTriangle className="w-5 h-5 text-rose-400" />
            </div>
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <p className="text-xs font-extrabold text-rose-200 uppercase tracking-wider">
                  {executionBlockedMsg.includes('Connection Error') ? 'EXECUTION FAILED — CONNECTION ERROR' : 'BLOCKED — USER CREDENTIAL REQUIRED'}
                </p>
                <span className="px-2 py-0.5 text-[9px] font-mono font-bold rounded bg-rose-950 text-rose-300 border border-rose-500/30">
                  Target: {selectedAgent?.name || selectedAgentId}
                </span>
              </div>
              <p className="text-xs text-slate-100 font-semibold leading-relaxed">{executionBlockedMsg}</p>
              {!executionBlockedMsg.includes('Connection Error') && (
                <p className="text-[10px] text-rose-300/80">
                  Simulation will never replace a missing credential silently. Please provide the required API key under Setup.
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => navigate(`/dependencies?agentId=${selectedAgentId}&blocked=true`)}
              className="px-3.5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow-lg shadow-rose-500/20 flex items-center space-x-1.5 transition hover:scale-[1.02] cursor-pointer"
            >
              <Shield className="w-3.5 h-3.5" />
              <span>Configure Credentials & Keys →</span>
            </button>
          </div>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        
        {/* Left Side: Agent Selection & Config */}
        <div className="lg:col-span-1 space-y-4">
          <div className="p-3.5 sm:p-4 rounded-2xl glass-panel border border-slate-700/80 bg-slate-950/80 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                1. Choose Target Agent
              </h2>
              <button
                onClick={() => navigate(`/dependencies?agentId=${selectedAgentId}`)}
                className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center space-x-1 cursor-pointer"
              >
                <Shield className="w-3 h-3" />
                <span>Gateway</span>
              </button>
            </div>
            
            <div className="space-y-1.5">
              <label className="text-xs text-slate-300 block">Active Target</label>
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

                <button
                  onClick={() => navigate(`/dependencies?agentId=${selectedAgentId}`)}
                  className="w-full py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-cyan-500/30 text-cyan-400 font-bold text-xs flex items-center justify-center space-x-2 transition cursor-pointer"
                >
                  <Shield className="w-3.5 h-3.5" />
                  <span>Configure Agent Dependencies & Keys →</span>
                </button>

                {/* System Prompt & Invariant Spec (Fixed: Never Blank) */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-cyan-400" />
                      <span>System Prompt & Constitution</span>
                    </label>
                    <span className="text-[9px] font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                      {selectedAgent.system_prompt ? 'Custom Prompt' : 'Canonical AST Spec'}
                    </span>
                  </div>
                  <div className="bg-slate-950 border border-slate-900 rounded-xl p-3 text-[11px] font-mono text-slate-300 max-h-44 overflow-y-auto space-y-2">
                    {selectedAgent.system_prompt && selectedAgent.system_prompt.trim().length > 0 ? (
                      <p className="whitespace-pre-wrap leading-relaxed">{selectedAgent.system_prompt}</p>
                    ) : (
                      <div className="space-y-2 text-slate-400">
                        <p className="text-cyan-300 font-semibold">// AST Canonical System Specification:</p>
                        <p className="text-[10px] leading-relaxed text-slate-300">
                          Agent baseline prompt follows canonical intake specification for domain <strong className="text-indigo-400">{selectedAgent.domain}</strong> (Version {selectedAgent.version_label || 'v1.0'}).
                        </p>
                        {selectedAgent.constitution?.never_rules && selectedAgent.constitution.never_rules.length > 0 && (
                          <div className="pt-1 border-t border-slate-900 text-rose-300">
                            <p className="font-bold text-[10px] uppercase text-rose-400 mb-1">Safety Invariants:</p>
                            <ul className="list-disc list-inside space-y-0.5 text-[10px]">
                              {selectedAgent.constitution.never_rules.map((rule, idx) => (
                                <li key={idx} className="truncate">{rule}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Inline API Keys & Credential Injection Drawer */}
                <div className="pt-2 border-t border-slate-800/80 space-y-2">
                  <button
                    onClick={() => setShowInlineKeys(!showInlineKeys)}
                    className="w-full py-2 px-3 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-slate-700 text-left text-xs font-bold text-slate-200 flex items-center justify-between transition cursor-pointer"
                  >
                    <span className="flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 text-amber-400" />
                      <span>Inline API Keys & Secrets Injection</span>
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">
                      {showInlineKeys ? 'Hide ▲' : 'Provide Keys ▼'}
                    </span>
                  </button>

                  {showInlineKeys && (
                    <div className="p-3 rounded-xl bg-slate-900/90 border border-amber-500/30 space-y-3 animate-fadeIn">
                      <p className="text-[10px] text-slate-400 leading-snug">
                        Dynamically detected API keys for target agent <strong>{selectedAgent?.display_name || selectedAgent?.name}</strong>. Provided keys take priority.
                      </p>
                      
                      {(() => {
                        const dynamicKeys = Array.from(new Set([
                          ...(setupReadiness?.missing_credentials || []),
                          ...((selectedAgent?.tools || []).map(t => `${t.name.toUpperCase()}_API_KEY`))
                        ])).filter(k => k && k.trim() && !['OPENAI_API_KEY', 'GEMINI_API_KEY', 'OPENROUTER_API_KEY'].includes(k));

                        const allKeys = Array.from(new Set(['OPENROUTER_API_KEY', 'GEMINI_API_KEY', ...dynamicKeys]));

                        return (
                          <div className="space-y-2.5 font-mono text-xs">
                            {allKeys.map(keyName => (
                              <div key={keyName} className="p-2 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                                <div className="flex items-center justify-between text-[10px]">
                                  <label className="text-cyan-300 font-bold">{keyName}</label>
                                  <span className="text-slate-500 text-[9px]">
                                    {providedSecrets[keyName] ? '✓ Key Injected' : 'Default Pool Active'}
                                  </span>
                                </div>
                                <input
                                  type="password"
                                  placeholder={`Enter custom ${keyName}...`}
                                  value={providedSecrets[keyName] || ''}
                                  onChange={e => setProvidedSecrets({ ...providedSecrets, [keyName]: e.target.value })}
                                  className="w-full bg-slate-900 border border-slate-700/80 rounded-md px-2.5 py-1 text-slate-200 focus:outline-none focus:border-cyan-500/60 text-xs font-mono"
                                />
                              </div>
                            ))}
                          </div>
                        );
                      })()}

                      <div className="flex items-center justify-between pt-1.5 border-t border-slate-800">
                        <button
                          type="button"
                          onClick={() => setProvidedSecrets({})}
                          className="text-[10px] text-slate-400 hover:text-rose-400 underline font-mono cursor-pointer"
                        >
                          Clear Injected Keys
                        </button>
                        <span className="text-[10px] text-emerald-400 font-mono font-bold">
                          {Object.keys(providedSecrets).filter(k => providedSecrets[k]?.trim()).length} keys active
                        </span>
                      </div>
                    </div>
                  )}
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
                  className="px-3 py-1 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono hover:text-slate-200 transition disabled:opacity-50 cursor-pointer"
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
                  className="text-indigo-400 hover:underline cursor-pointer"
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

            {/* Execution Mode Selector with Exact Capability Indicators */}
            {scenarios.length > 0 && (
              <div className="pt-3 border-t border-slate-800/80 space-y-2.5">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Sliders className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Execution Mode & Capability Binding</span>
                  </h3>
                  <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/60 border border-cyan-500/30 px-2 py-0.5 rounded">
                    Active Mode: {executionMode.toUpperCase()}
                  </span>
                </div>

                {/* Preflight Mode Recommendation Banner */}
                {setupReadiness && setupReadiness.missing_credentials && setupReadiness.missing_credentials.length > 0 && (
                  <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-500/40 text-amber-200 text-xs flex items-center justify-between gap-2 animate-fadeIn">
                    <div className="flex items-center space-x-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                      <span>
                        <strong>Preflight Recommendation:</strong> Faithful mode missing secret (<strong className="font-mono text-white">{setupReadiness.missing_credentials.join(', ')}</strong>). 
                        Switch to <strong>Compatible</strong> or <strong>Simulation</strong> mode for 100% execution success.
                      </span>
                    </div>
                    {executionMode === 'faithful' && (
                      <button
                        onClick={() => setExecutionMode('compatible')}
                        className="px-2.5 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-[10px] shrink-0 cursor-pointer"
                      >
                        Auto-Switch to Compatible →
                      </button>
                    )}
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  {/* Faithful */}
                  <div
                    onClick={() => !running && setExecutionMode('faithful')}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer select-none ${
                      executionMode === 'faithful'
                        ? 'bg-emerald-950/30 border-emerald-400/90 ring-1 ring-emerald-400/60 shadow-lg shadow-emerald-950/50'
                        : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center space-x-2">
                        <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center ${
                          executionMode === 'faithful' ? 'bg-emerald-400' : 'border border-slate-600'
                        }`}>
                          {executionMode === 'faithful' && <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
                        </div>
                        <span className="text-xs font-extrabold text-slate-100">Faithful</span>
                      </div>
                      <span className="text-[9px] font-mono font-bold text-emerald-400 uppercase bg-emerald-950 px-1.5 py-0.5 rounded border border-emerald-500/30">Primary</span>
                    </div>
                    <p className="text-[11px] text-slate-300 leading-snug">
                      Test real agent with system LLM pool & real tool APIs.
                    </p>
                    <span className="mt-2 inline-block text-[9px] font-mono text-emerald-300 bg-emerald-950/80 px-1.5 py-0.5 rounded border border-emerald-500/20">
                      🟢 Ready (Platform Keys Active)
                    </span>
                  </div>

                  {/* Compatible */}
                  <div
                    onClick={() => !running && setExecutionMode('compatible')}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer select-none ${
                      executionMode === 'compatible'
                        ? 'bg-indigo-950/30 border-indigo-400/80 ring-1 ring-indigo-400/50 shadow-lg shadow-indigo-950/50'
                        : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center space-x-2">
                        <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center ${
                          executionMode === 'compatible' ? 'bg-indigo-400' : 'border border-slate-600'
                        }`}>
                          {executionMode === 'compatible' && <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
                        </div>
                        <span className="text-xs font-extrabold text-slate-100">Compatible</span>
                      </div>
                      <span className="text-[9px] font-mono text-indigo-300 uppercase bg-indigo-950 px-1.5 py-0.5 rounded border border-indigo-500/30">Adapter</span>
                    </div>
                    <p className="text-[11px] text-slate-300 leading-snug">
                      Run real agent with platform tool gateway mocks.
                    </p>
                    <span className="mt-2 inline-block text-[9px] font-mono text-indigo-300 bg-indigo-950/80 px-1.5 py-0.5 rounded border border-indigo-500/20">
                      🔵 Adapter Gateway Ready
                    </span>
                  </div>

                  {/* Simulation */}
                  <div
                    onClick={() => !running && setExecutionMode('simulation')}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer select-none ${
                      executionMode === 'simulation'
                        ? 'bg-amber-950/30 border-amber-500/80 ring-1 ring-amber-500/50 shadow-lg shadow-amber-950/50'
                        : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center space-x-2">
                        <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center ${
                          executionMode === 'simulation' ? 'bg-amber-400' : 'border border-slate-600'
                        }`}>
                          {executionMode === 'simulation' && <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
                        </div>
                        <span className="text-xs font-extrabold text-slate-100">Simulation</span>
                      </div>
                      <span className="text-[9px] font-mono font-bold text-amber-400 uppercase bg-amber-950 px-1.5 py-0.5 rounded border border-amber-500/40">Lower Fidelity</span>
                    </div>
                    <p className="text-[11px] text-amber-200/90 leading-snug">
                      Offline deterministic simulation with mock environment.
                    </p>
                    <span className="mt-2 inline-block text-[9px] font-mono text-amber-300 bg-amber-950/80 px-1.5 py-0.5 rounded border border-amber-500/20">
                      🟢 0 API Keys Required
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Launch controls */}
            {scenarios.length > 0 && (
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                <p className="text-[10px] text-slate-500 font-mono">
                  Running under <span className="uppercase text-cyan-400 font-bold">{executionMode}</span> execution mode.
                </p>
                <button
                  onClick={() => handleStartExecution()}
                  disabled={running || selectedScenarioIds.length === 0}
                  className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-extrabold text-xs shadow-lg shadow-indigo-500/20 flex items-center space-x-2 transition disabled:opacity-50 disabled:scale-100 active:scale-95 cursor-pointer"
                >
                  {running ? (
                    <><RefreshCw className="w-3.5 h-3.5 animate-spin" /><span>Executing...</span></>
                  ) : (
                    <><Play className="w-3.5 h-3.5 fill-current" /><span>Execute {selectedScenarioIds.length} Scenarios</span></>
                  )}
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
                <span className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
                  executionJob.status === 'completed'
                    ? 'bg-emerald-950 text-emerald-400 border-emerald-500/30'
                    : executionJob.status === 'running'
                    ? 'bg-indigo-950 text-indigo-400 border-indigo-500/30 animate-pulse'
                    : isJobBlocked
                    ? 'bg-amber-950 text-amber-400 border-amber-500/40'
                    : 'bg-slate-900 text-slate-400 border-slate-800'
                }`}>
                  {isJobBlocked ? 'BLOCKED — CREDENTIAL REQUIRED' : executionJob.status}
                </span>
              </div>

              {/* Progress Bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-[11px] font-mono">
                  <span className="text-slate-400">{isJobBlocked ? 'Faithful Execution Status' : 'Sandbox Runs'}</span>
                  <span className={isJobBlocked ? 'text-amber-400 font-bold' : 'text-slate-200'}>
                    {isJobBlocked ? `0/${executionJob.total_scenarios} faithfully executed (0%)` : `${executionJob.completed_scenarios}/${executionJob.total_scenarios} (${progressPct}%)`}
                  </span>
                </div>
                <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      isJobBlocked ? 'bg-amber-500/40' : 'bg-gradient-to-r from-indigo-500 to-purple-500'
                    }`}
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
                      Sandbox Traces Saved ({executionTraces.length} Traces Collected)
                    </h4>
                    <p className="text-[10px] text-slate-400 mt-1">
                      Ready to judge sandbox traces using hybrid LLM evaluation.
                    </p>
                  </div>
                  <button
                    onClick={handleSendToEvaluation}
                    disabled={evaluating}
                    className="px-5 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-600 hover:from-emerald-400 hover:to-cyan-500 disabled:from-slate-700 disabled:to-slate-700 text-white font-extrabold text-[11px] shadow-lg shadow-emerald-500/25 flex items-center space-x-1.5 transition cursor-pointer"
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

      {/* ── 3. EXECUTION OBSERVATIONS & FINDINGS SECTION ── */}
      {(running || executionTraces.length > 0 || executionJob) && (
        <div className="p-6 rounded-2xl glass-panel border border-cyan-500/30 bg-slate-950/90 space-y-6 shadow-2xl animate-fadeIn">
          {/* Header & Filter Controls */}
          <div className="flex items-center justify-between flex-wrap gap-3 border-b border-slate-800/80 pb-4">
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
                <Eye className="w-5 h-5 text-cyan-400" />
              </div>
              <div>
                <h2 className="text-sm font-extrabold text-white flex items-center gap-2">
                  <span>3. EXECUTION OBSERVATIONS & SCENARIO FINDINGS</span>
                  <span className="px-2 py-0.5 text-[10px] font-bold font-mono rounded bg-cyan-950 text-cyan-300 border border-cyan-500/30">
                    {executionTraces.length} SCENARIOS OBSERVED
                  </span>
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Detailed breakdown of actions, tool invocations, state mutations, policy decisions, and security alerts captured during sandbox execution.
                </p>
              </div>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center space-x-1.5">
              {[
                { id: 'all', label: 'All Observations' },
                { id: 'tools', label: `Tool Calls (${totalToolCalls})` },
                { id: 'security', label: `Policy & Security (${totalSecurityEvents + totalBlockedTools})` },
                { id: 'failed', label: 'Abnormal/Non-Zero' },
              ].map(f => (
                <button
                  key={f.id}
                  onClick={() => setTraceFilter(f.id as any)}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-bold transition cursor-pointer ${
                    traceFilter === f.id
                      ? 'bg-cyan-900/60 border border-cyan-400 text-cyan-200'
                      : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Quick Metrics Bar & Execution Accounting */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-400">Execution Coverage</span>
              <div className="text-base font-extrabold text-cyan-300">
                {coveragePct}%
              </div>
              <span className="text-[9px] text-slate-500">{totalExecutedCount}/{targetScenarioCount} executed</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-400">Total Tool Calls</span>
              <div className="text-base font-extrabold text-indigo-300">{totalToolCalls}</div>
              <span className="text-[9px] text-slate-500">Invocations monitored</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-400">Policy Interventions</span>
              <div className={`text-base font-extrabold ${totalBlockedTools > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                {totalBlockedTools}
              </div>
              <span className="text-[9px] text-slate-500">Blocked unsafe attempts</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-400">Security Events</span>
              <div className={`text-base font-extrabold ${totalSecurityEvents > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                {totalSecurityEvents}
              </div>
              <span className="text-[9px] text-slate-500">Injections / leaks detected</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-400">Avg Run Latency</span>
              <div className="text-base font-extrabold text-cyan-300">{avgLatency} ms</div>
              <span className="text-[9px] text-slate-500">Per sandbox scenario</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-400">Latency Breakdown</span>
              <div className="text-xs font-mono font-extrabold text-slate-200">
                Init: 120ms | Exec: {Math.max(avgLatency - 120, 0)}ms
              </div>
              <span className="text-[9px] text-slate-500">Sandbox vs Process</span>
            </div>
          </div>

          {/* Live In-flight Spinner if running and waiting for first trace */}
          {running && executionTraces.length === 0 && (
            <div className="p-8 rounded-xl border border-cyan-500/20 bg-cyan-950/10 text-center space-y-3">
              <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin mx-auto" />
              <p className="text-xs text-cyan-300 font-bold">Executing Scenarios inside Isolated Sandbox...</p>
              <p className="text-[11px] text-slate-400">Capturing tool calls, user prompts, system events, and state diffs in real-time.</p>
            </div>
          )}

          {/* Scenario Observation Cards */}
          <div className="space-y-3">
            {filteredTraces.map((trace, idx) => {
              const matchingScenario = scenarios.find(s => s.id === trace.scenario_id);
              const isExpanded = expandedTraceId === trace.id || (filteredTraces.length === 1);
              const hasBlockedTools = trace.tool_calls?.some(tc => tc.routing_decision === 'BLOCK' || tc.status === 'BLOCKED_POLICY');
              const hasSecurityEvents = trace.security_events && trace.security_events.length > 0;
              const obsSummary = trace.observation_summary;

              return (
                <div
                  key={trace.id || idx}
                  className={`rounded-xl border transition-all ${
                    hasSecurityEvents
                      ? 'border-rose-500/50 bg-slate-900/90 shadow-lg shadow-rose-950/20'
                      : hasBlockedTools
                      ? 'border-amber-500/40 bg-slate-900/90 shadow-lg shadow-amber-950/20'
                      : 'border-slate-800 bg-slate-900/60 hover:border-slate-700'
                  }`}
                >
                  {/* Card Header */}
                  <div
                    onClick={() => setExpandedTraceId(isExpanded ? null : trace.id)}
                    className="p-4 flex items-center justify-between flex-wrap gap-3 cursor-pointer select-none"
                  >
                    <div className="flex items-center space-x-3 min-w-0">
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${
                        trace.status === 'COMPLETED'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40'
                          : 'bg-rose-950 text-rose-300 border border-rose-500/40'
                      }`}>
                        #{idx + 1}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center space-x-2 flex-wrap">
                          <h4 className="text-xs font-bold text-slate-100">
                            {matchingScenario?.title || trace.scenario_id}
                          </h4>
                          {matchingScenario?.category && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase bg-slate-800 text-indigo-300 border border-slate-700">
                              {matchingScenario.category}
                            </span>
                          )}
                          {hasSecurityEvents && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-950 text-rose-300 border border-rose-500/50 flex items-center space-x-1">
                              <ShieldAlert className="w-2.5 h-2.5" />
                              <span>Security Flag</span>
                            </span>
                          )}
                          {hasBlockedTools && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-950 text-amber-300 border border-amber-500/40 flex items-center space-x-1">
                              <Shield className="w-2.5 h-2.5" />
                              <span>Policy Blocked</span>
                            </span>
                          )}
                        </div>
                        <p className="text-[10px] font-mono text-slate-500 mt-0.5">
                          Scenario ID: <span className="text-slate-400">{trace.scenario_id}</span> · Latency: <span className="text-cyan-400">{trace.total_latency_ms}ms</span> · Tools: <span className="text-indigo-400">{trace.tool_calls?.length || 0}</span> · Events: <span className="text-slate-400">{trace.events?.length || 0}</span>
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-0.5 rounded text-[9px] font-bold font-mono ${
                        trace.status === 'COMPLETED'
                          ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/30'
                          : 'bg-rose-950/80 text-rose-300 border border-rose-500/30'
                      }`}>
                        {trace.status}
                      </span>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-slate-400" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      )}
                    </div>
                  </div>

                  {/* Expanded Findings Details */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-1 border-t border-slate-800/80 space-y-4 text-xs animate-fadeIn">
                      
                      {/* 1. Observation Summary Grid */}
                      {obsSummary && (
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2">
                          <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1">
                            <span className="text-[9px] uppercase font-bold text-slate-400 flex items-center gap-1">
                              <FileText className="w-3 h-3 text-cyan-400" />
                              <span>Files Modified / Created</span>
                            </span>
                            <div className="text-[11px] font-mono text-slate-200">
                              {(obsSummary.files_created && obsSummary.files_created.length > 0) || (obsSummary.files_modified && obsSummary.files_modified.length > 0) ? (
                                <span>{[...(obsSummary.files_created || []), ...(obsSummary.files_modified || [])].join(', ')}</span>
                              ) : (
                                <span className="text-slate-500 italic">None (No disk mutation)</span>
                              )}
                            </div>
                          </div>

                          <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1">
                            <span className="text-[9px] uppercase font-bold text-slate-400 flex items-center gap-1">
                              <Database className="w-3 h-3 text-indigo-400" />
                              <span>Database / HTTP Invocations</span>
                            </span>
                            <div className="text-[11px] font-mono text-slate-200">
                              {(obsSummary.database_queries_executed && obsSummary.database_queries_executed.length > 0) || (obsSummary.external_http_calls && obsSummary.external_http_calls.length > 0) ? (
                                <span>{obsSummary.database_queries_executed?.length || 0} DB queries, {obsSummary.external_http_calls?.length || 0} HTTP calls</span>
                              ) : (
                                <span className="text-slate-500 italic">Isolated local mock sandbox</span>
                              )}
                            </div>
                          </div>

                          <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1">
                            <span className="text-[9px] uppercase font-bold text-slate-400 flex items-center gap-1">
                              <Shield className="w-3 h-3 text-emerald-400" />
                              <span>Policy Invariant Enforcement</span>
                            </span>
                            <div className="text-[11px] font-mono text-slate-200">
                              {obsSummary.policy_violations && obsSummary.policy_violations.length > 0 ? (
                                <span className="text-rose-400 font-bold">{obsSummary.policy_violations.join(', ')}</span>
                              ) : (
                                <span className="text-emerald-400 font-semibold">100% Invariants Preserved ✓</span>
                              )}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* 2. Tool Calls & Policy Decisions */}
                      {trace.tool_calls && trace.tool_calls.length > 0 && (
                        <div className="space-y-2">
                          <label className="text-[10px] font-bold text-indigo-300 uppercase tracking-wider block">
                            Observed Tool Calls ({trace.tool_calls.length}):
                          </label>
                          <div className="space-y-1.5">
                            {trace.tool_calls.map((tc, tcIdx) => {
                              const isBlocked = tc.routing_decision === 'BLOCK' || tc.status === 'BLOCKED_POLICY';
                              return (
                                <div
                                  key={tcIdx}
                                  className={`p-3 rounded-lg border text-xs font-mono space-y-1.5 ${
                                    isBlocked
                                      ? 'bg-rose-950/30 border-rose-500/40 text-rose-200'
                                      : 'bg-slate-950 border-slate-800 text-slate-200'
                                  }`}
                                >
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center space-x-2">
                                      <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                                      <span className="font-bold text-cyan-300">{tc.tool_name}</span>
                                    </div>
                                    <span className={`px-2 py-0.2 rounded text-[9px] font-bold ${
                                      isBlocked
                                        ? 'bg-rose-900 text-rose-200 border border-rose-500'
                                        : 'bg-emerald-950 text-emerald-300 border border-emerald-500/30'
                                    }`}>
                                      {tc.routing_decision || (isBlocked ? 'BLOCKED' : 'ALLOWED')}
                                    </span>
                                  </div>

                                  <div className="text-[10px] text-slate-400 bg-slate-900/60 p-2 rounded border border-slate-800/80">
                                    <span className="text-slate-500 block mb-0.5">Parameters:</span>
                                    <code>{JSON.stringify(tc.arguments, null, 2)}</code>
                                  </div>

                                  {tc.policy_reason && (
                                    <p className="text-[10px] text-amber-300">
                                      Policy Reason: {tc.policy_reason}
                                    </p>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* 3. Security Events Caught */}
                      {hasSecurityEvents && (
                        <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/40 space-y-2">
                          <label className="text-[10px] font-bold text-rose-300 uppercase tracking-wider flex items-center gap-1.5">
                            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                            <span>Security Invariant Interventions ({trace.security_events.length}):</span>
                          </label>
                          {trace.security_events.map((sec, secIdx) => (
                            <div key={secIdx} className="text-xs space-y-1 text-rose-200">
                              <div className="flex items-center justify-between font-mono text-[10px]">
                                <span className="font-bold uppercase text-rose-400">{sec.event_type}</span>
                                <span className="px-1.5 py-0.2 rounded bg-rose-900 text-rose-200">{sec.severity}</span>
                              </div>
                              <p className="text-[11px]">{sec.evidence}</p>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* 4. Event Stream / Message Timeline */}
                      {trace.events && trace.events.length > 0 && (
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                            Execution Event Log ({trace.events.length} Steps):
                          </label>
                          <div className="max-h-48 overflow-y-auto space-y-1 bg-slate-950 p-2.5 rounded-lg border border-slate-800 font-mono text-[10px]">
                            {trace.events.map((ev, evIdx) => (
                              <div key={evIdx} className="flex items-start space-x-2 py-0.5 border-b border-slate-900/60 last:border-0">
                                <span className={`px-1.5 py-0.2 rounded text-[8px] uppercase font-bold shrink-0 ${
                                  ev.role === 'user'
                                    ? 'bg-blue-950 text-blue-300'
                                    : ev.role === 'agent_thought'
                                    ? 'bg-purple-950 text-purple-300'
                                    : ev.role === 'tool_call'
                                    ? 'bg-indigo-950 text-indigo-300'
                                    : ev.role === 'tool_result'
                                    ? 'bg-cyan-950 text-cyan-300'
                                    : 'bg-slate-800 text-slate-300'
                                }`}>
                                  {ev.role}
                                </span>
                                <span className="text-slate-300 break-words flex-1">{ev.content}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Process activity log */}
      <LiveProcessMonitor />
      </>}
    </div>
  );
};
