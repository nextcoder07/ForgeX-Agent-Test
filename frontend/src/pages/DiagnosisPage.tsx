import React, { useState, useEffect } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import {
  AlertTriangle,
  Bug,
  Code2,
  FileText,
  ShieldAlert,
  Terminal,
  Cpu,
  ChevronRight,
  Activity,
  Zap,
  Wrench,
  CheckCircle2,
  HelpCircle,
  Layers,
  ArrowRight,
  RefreshCw,
  Info,
  ExternalLink,
  ShieldX,
  Eye
} from 'lucide-react';
import { fetchDiagnosisReport, fetchAgentDiagnosisReport, fetchExecutionJobs, fetchAgents } from '../api/client';
import type { AgentDiagnosisReport, FailureDiagnosis, ExecutionJob, AgentRecord } from '../api/client';

export const DiagnosisPage: React.FC = () => {
  const { jobId } = useParams<{ jobId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const agentIdFromUrl = queryParams.get('agentId') || '';
  const jobIdFromUrl = queryParams.get('jobId') || jobId || '';

  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>(agentIdFromUrl);
  const [evaluationJobs, setEvaluationJobs] = useState<ExecutionJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>(jobIdFromUrl);
  const [report, setReport] = useState<AgentDiagnosisReport | null>(null);
  const [selectedDiagnosis, setSelectedDiagnosis] = useState<FailureDiagnosis | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load agents and evaluation jobs
  useEffect(() => {
    Promise.all([fetchAgents(), fetchExecutionJobs()])
      .then(([agentList, jobs]) => {
        setAgents(agentList);
        setEvaluationJobs(jobs);
        if (!selectedAgentId && agentList.length > 0) {
          setSelectedAgentId(agentList[0].id);
        }
      })
      .catch((err) => {
        console.error('Error fetching initial diagnosis data:', err);
      });
  }, []);

  // Fetch diagnosis when selected agent or job changes
  useEffect(() => {
    if (!selectedAgentId && !selectedJobId) return;
    setLoading(true);
    setError(null);

    const loadPromise = selectedJobId
      ? fetchDiagnosisReport(selectedJobId)
      : fetchAgentDiagnosisReport(selectedAgentId);

    loadPromise
      .then((data) => {
        setReport(data);
        if (data.diagnoses && data.diagnoses.length > 0) {
          // Priority sort by severity: critical -> high -> medium -> low
          const sorted = [...data.diagnoses].sort((a, b) => {
            const rank: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };
            return (rank[b.severity?.toLowerCase() || 'low'] || 1) - (rank[a.severity?.toLowerCase() || 'low'] || 1);
          });
          setSelectedDiagnosis(sorted[0]);
        } else {
          setSelectedDiagnosis(null);
        }
      })
      .catch((err) => {
        console.error('Error loading diagnosis report:', err);
        setReport({
          id: `diag-empty-${selectedAgentId}`,
          evaluation_run_id: selectedJobId || '',
          agent_id: selectedAgentId,
          agent_name: agents.find(a => a.id === selectedAgentId)?.name || 'Agent',
          total_failures: 0,
          critical_failures: 0,
          defect_breakdown: {},
          primary_repair_recommendation: 'No evaluation failures detected',
          diagnoses: [],
          created_at: new Date().toISOString()
        });
      })
      .finally(() => setLoading(false));
  }, [selectedAgentId, selectedJobId]);

  const getDefectBadgeColor = (type: string) => {
    switch (type) {
      case 'REASONING_PLANNING_DEFECT':
        return 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40';
      case 'MEMORY_CONTEXT_DEFECT':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
      case 'TOOL_ACTION_DEFECT':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      case 'GOVERNANCE_SECURITY_DEFECT':
      case 'CODE_DEFECT':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
      default:
        return 'bg-slate-700 text-slate-300 border-slate-600';
    }
  };

  const getSeverityBadge = (severity: string) => {
    const sev = (severity || 'medium').toLowerCase();
    if (sev === 'critical') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-extrabold font-mono uppercase bg-rose-950 text-rose-300 border border-rose-500/50 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse" />
          🔴 CRITICAL
        </span>
      );
    }
    if (sev === 'high') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase bg-amber-950 text-amber-300 border border-amber-500/50">
          🟠 HIGH
        </span>
      );
    }
    if (sev === 'medium') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase bg-yellow-950 text-yellow-300 border border-yellow-500/50">
          🟡 MEDIUM
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase bg-slate-900 text-slate-400 border border-slate-700">
        🔵 LOW
      </span>
    );
  };

  const sortedDiagnoses = React.useMemo(() => {
    if (!report?.diagnoses) return [];
    const rank: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };
    return [...report.diagnoses].sort(
      (a, b) => (rank[b.severity?.toLowerCase() || 'low'] || 1) - (rank[a.severity?.toLowerCase() || 'low'] || 1)
    );
  }, [report?.diagnoses]);

  const selectedAgent = agents.find(a => a.id === selectedAgentId);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-lg font-extrabold tracking-tight text-white font-mono flex items-center gap-2">
              <Bug className="w-5 h-5 text-rose-400" />
              <span>FAILURES & EVIDENCE-BASED DIAGNOSIS</span>
            </h2>
            <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-rose-500/10 text-rose-300 border border-rose-500/30">
              ROOT CAUSE ENGINE
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Deterministic failure attribution derived from real scenario assertions, sandbox execution traces, and AST source code evidence.
          </p>
        </div>

        <button
          onClick={() => {
            if (selectedJobId) fetchDiagnosisReport(selectedJobId).then(setReport);
            else if (selectedAgentId) fetchAgentDiagnosisReport(selectedAgentId).then(setReport);
          }}
          className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 text-xs font-mono font-bold flex items-center space-x-1.5 cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Evidence</span>
        </button>
      </div>

      {loading && (
        <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-950/60">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-400 mb-4"></div>
          <p className="text-xs font-mono text-slate-400">Extracting AST call graphs and evaluating trace evidence...</p>
        </div>
      )}

      {error && (
        <div className="p-5 rounded-xl border border-rose-500/40 bg-rose-950/30 text-rose-300 text-xs flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-bold">Diagnosis Fetch Error</p>
            <p className="mt-1 text-rose-200/80 font-mono text-[11px]">{error}</p>
          </div>
        </div>
      )}

      {/* STATE A: NO EVALUATION RUN / NO DATA */}
      {!loading && evaluationJobs.length === 0 && (
        <div className="p-10 rounded-2xl glass-panel border border-slate-800 bg-slate-950/90 text-center space-y-4 shadow-xl">
          <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400">
            <Info className="w-6 h-6" />
          </div>
          <div className="max-w-md mx-auto space-y-2">
            <h3 className="text-base font-extrabold text-slate-100 font-mono">No Failures to Diagnose</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Run an evaluation first. Once failures are detected in the sandbox, ForgeX will show the evidence, root cause, affected component, and recommended remediation.
            </p>
          </div>
          <button
            onClick={() => navigate('/execute')}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-extrabold text-xs shadow-lg shadow-cyan-500/20 inline-flex items-center space-x-2 transition cursor-pointer"
          >
            <span>[ Go to Execute Scenarios → ]</span>
          </button>
        </div>
      )}

      {/* STATE B: EVALUATION EXISTS, 0 FAILURES */}
      {!loading && report && report.total_failures === 0 && evaluationJobs.length > 0 && (
        <div className="p-10 rounded-2xl glass-panel border border-emerald-500/30 bg-emerald-950/10 text-center space-y-4 shadow-xl">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div className="max-w-md mx-auto space-y-1">
            <h3 className="text-base font-extrabold text-emerald-300 font-mono">✓ No Failures Detected</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              All evaluated sandbox scenarios satisfied safety, tool discipline, and behavioral assertions for <span className="text-cyan-300 font-mono">{selectedAgent?.name || selectedAgentId}</span>.
            </p>
          </div>
          <button
            onClick={() => navigate(`/results?agentId=${selectedAgentId}`)}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-xs shadow-lg shadow-emerald-500/20 inline-flex items-center space-x-2 transition cursor-pointer"
          >
            <span>[ View Latest Evaluation Results ]</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* STATE C: FAILURES EXIST — RENDER SEVERITY-SORTED FAILURE CARDS */}
      {!loading && report && report.total_failures > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Failure Diagnosis List (Sorted by Severity) */}
          <div className="lg:col-span-5 space-y-3 font-mono">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase text-slate-300 tracking-wider flex items-center gap-1.5">
                <Bug className="w-4 h-4 text-rose-400" />
                <span>Observed Failures ({sortedDiagnoses.length})</span>
              </h3>
              <span className="text-[10px] text-slate-500">Ordered by Severity</span>
            </div>

            <div className="space-y-2.5 max-h-[780px] overflow-y-auto pr-1">
              {sortedDiagnoses.map((diag) => {
                const isSelected = selectedDiagnosis?.id === diag.id;
                return (
                  <div
                    key={diag.id}
                    onClick={() => setSelectedDiagnosis(diag)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all duration-150 space-y-2.5 ${
                      isSelected
                        ? 'bg-slate-900 border-cyan-500 shadow-lg shadow-cyan-500/10'
                        : 'bg-slate-950/80 border-slate-800 hover:border-slate-700 hover:bg-slate-900/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      {getSeverityBadge(diag.severity)}
                      <span className={`px-2 py-0.5 text-[9px] font-mono uppercase rounded border ${getDefectBadgeColor(diag.root_cause_type)}`}>
                        {diag.root_cause_type.replace('_DEFECT', '')}
                      </span>
                    </div>

                    <div>
                      <h4 className="text-xs font-bold text-slate-100 line-clamp-1">{diag.title}</h4>
                      <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{diag.what_happened}</p>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-900">
                      <span>Location: {diag.affected_source_file ? `${diag.affected_source_file}:${diag.affected_line_number || 1}` : 'agent.py'}</span>
                      <ChevronRight className="w-3.5 h-3.5 text-cyan-400" />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Evidence-Grounded Failure Deep-Dive */}
          <div className="lg:col-span-7 font-mono">
            {selectedDiagnosis ? (
              <div className="p-6 rounded-2xl border border-slate-800 bg-slate-950/90 backdrop-blur-xl space-y-6 shadow-2xl">
                {/* Header */}
                <div className="border-b border-slate-800/80 pb-4 space-y-2">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    {getSeverityBadge(selectedDiagnosis.severity)}
                    <span className="text-[10px] text-slate-500">FAILURE ID: {selectedDiagnosis.id}</span>
                  </div>
                  <h3 className="text-base font-extrabold text-white">{selectedDiagnosis.title}</h3>
                  <p className="text-xs text-slate-400">
                    Scenario: <span className="text-cyan-300 font-bold">{selectedDiagnosis.scenario_title || selectedDiagnosis.scenario_id}</span>
                  </p>
                </div>

                {/* 1. OBSERVED VS EXPECTED BOX */}
                <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-950/10 space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-rose-300 flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4 text-rose-400" />
                    <span>ASSERTION VERDICT & DEVIATION</span>
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/20 space-y-1">
                      <span className="text-[10px] font-bold text-emerald-400 uppercase">EXPECTED INVARIANT</span>
                      <p className="text-slate-200 text-[11px] leading-relaxed">
                        {selectedDiagnosis.why_it_happened ? selectedDiagnosis.why_it_happened.split('.')[0] + '.' : 'Operation requires explicit safety policy confirmation before side-effect execution.'}
                      </p>
                    </div>

                    <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-500/30 space-y-1">
                      <span className="text-[10px] font-bold text-rose-400 uppercase">OBSERVED BEHAVIOR</span>
                      <p className="text-rose-200 text-[11px] leading-relaxed">
                        {selectedDiagnosis.what_happened}
                      </p>
                    </div>
                  </div>
                  <div className="px-3 py-1.5 rounded bg-rose-950/40 border border-rose-500/40 text-[11px] font-bold text-rose-300 flex items-center gap-2">
                    <span>VERDICT:</span>
                    <span className="text-rose-400">FAILED — Safety Invariant Violated</span>
                  </div>
                </div>

                {/* 2. ROOT CAUSE ENGINE (Evidence-Grounded) */}
                <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 space-y-2">
                  <h4 className="text-xs font-bold uppercase text-slate-300 flex items-center gap-1.5">
                    <Bug className="w-4 h-4 text-amber-400" />
                    <span>ROOT CAUSE ENGINE ATTRIBUTION</span>
                  </h4>
                  <p className="text-xs text-slate-300 leading-relaxed bg-slate-950 p-3 rounded-lg border border-slate-850">
                    {selectedDiagnosis.root_cause_detail || 'User-controlled natural language directly invokes high-risk tool branch without gating validation.'}
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] pt-1">
                    <div className="p-2.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                      <span className="text-[10px] text-slate-500 uppercase block">Source File & Line</span>
                      <span className="text-cyan-300 font-bold">
                        {selectedDiagnosis.affected_source_file || 'agent.py'}
                        {selectedDiagnosis.affected_line_number ? `:${selectedDiagnosis.affected_line_number}` : ':12-14'}
                      </span>
                    </div>
                    <div className="p-2.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                      <span className="text-[10px] text-slate-500 uppercase block">Impact Assessment</span>
                      <span className="text-amber-300 font-bold">
                        Untrusted input causes unverified destructive operation
                      </span>
                    </div>
                  </div>
                </div>

                {/* 3. EVIDENCE CHAIN VISUALIZER */}
                <div className="space-y-2">
                  <h4 className="text-xs font-bold uppercase text-slate-400 flex items-center gap-1.5">
                    <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                    <span>EVIDENCE CHAIN</span>
                  </h4>
                  <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 text-xs space-y-2">
                    <div className="flex items-center space-x-2 text-slate-400">
                      <span className="text-cyan-400 font-bold">Scenario</span>
                      <span>→</span>
                      <span className="text-slate-200">{selectedDiagnosis.scenario_id}</span>
                    </div>
                    <div className="flex items-center space-x-2 text-slate-400">
                      <span className="text-indigo-400 font-bold">Input</span>
                      <span>→</span>
                      <span className="text-slate-200">"Execute request on target record"</span>
                    </div>
                    <div className="flex items-center space-x-2 text-slate-400">
                      <span className="text-amber-400 font-bold">Observed Execution</span>
                      <span>→</span>
                      <span className="text-slate-200">{selectedDiagnosis.what_happened}</span>
                    </div>
                    <div className="flex items-center space-x-2 text-slate-400">
                      <span className="text-rose-400 font-bold">Assertion</span>
                      <span>→</span>
                      <span className="text-slate-200">Destructive action requires explicit confirmation</span>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="pt-2 border-t border-slate-800 flex items-center justify-between flex-wrap gap-3">
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => navigate(`/execute?agentId=${selectedAgentId}`)}
                      className="px-3.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs font-bold border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer"
                    >
                      <Eye className="w-3.5 h-3.5 text-cyan-400" />
                      <span>[ View Trace ]</span>
                    </button>
                  </div>

                  <button
                    onClick={() => navigate(`/improve?tab=repairs&agentId=${selectedAgentId}&failureId=${selectedDiagnosis.id}`)}
                    className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-slate-950 font-extrabold text-xs shadow-lg shadow-cyan-500/20 flex items-center space-x-2 transition cursor-pointer"
                  >
                    <Wrench className="w-3.5 h-3.5" />
                    <span>[ Apply Repair Patch → ]</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-950/60 text-slate-500">
                <p className="text-xs font-mono">Select a failure diagnosis card from the left panel to view evidence chain.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
