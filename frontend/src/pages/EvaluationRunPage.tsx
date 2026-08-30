import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams, useLocation } from "react-router-dom";
import {
  Zap,
  BarChart3,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Clock,
  Cpu,
  Shield,
  ChevronDown,
  ChevronRight,
  Wrench,
  Info,
  Sliders,
  Check,
  Ban,
  HelpCircle,
  AlertOctagon,
  Eye,
  X,
  Database,
  Trash2
} from 'lucide-react';
import type { PageId } from '../components/Navbar';
import type { AgentRecord, ReliabilityScorecard, FailureCluster, FailureFinding } from '../api/client';
import {
  fetchAgents,
  runEvaluationJob,
  evaluateExecutionJob,
  fetchLatestExecutionJob,
  fetchScorecard,
  fetchFailureClusters,
  fetchEvaluationJobs,
  fetchEvaluationJobDetails,
  fetchEvaluationVerdicts,
  fetchEvaluationTracesDetails,
  fetchEvaluationReport,
  deleteEvaluationJob,
} from '../api/client';
import { TwoAxisQuadrant } from '../components/TwoAxisQuadrant';
import { FailureClustersView } from '../components/FailureClustersView';
import { LiveProcessMonitor } from '../components/LiveProcessMonitor';

interface EvaluationRunPageProps {
  jobId?: string;
}

export const EvaluationRunPage: React.FC<EvaluationRunPageProps> = ({}) => {
  const { jobId } = useParams<{ jobId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const agentIdFromUrl = queryParams.get('agentId');

  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [evaluationJobs, setEvaluationJobs] = useState<any[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>(jobId || '');
  const [batchSize, setBatchSize] = useState(34);
  const [evalJob, setEvalJob] = useState<any | null>(null);
  const [scorecard, setScorecard] = useState<ReliabilityScorecard | null>(null);
  const [report, setReport] = useState<any | null>(null);
  const [verdicts, setVerdicts] = useState<any[]>([]);
  const [traces, setTraces] = useState<any[]>([]);
  const [clusters, setClusters] = useState<FailureCluster[]>([]);
  const [resultsError, setResultsError] = useState('');
  const [running, setRunning] = useState(false);
  const [userDeclinedRepair, setUserDeclinedRepair] = useState(false);
  const [expandedScenarioId, setExpandedScenarioId] = useState<string | null>(null);
  const [inspectFinding, setInspectFinding] = useState<FailureFinding | null>(null);

  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    fetchAgents().then((list) => {
      setAgents(list);
      if (agentIdFromUrl && list.some(a => a.id === agentIdFromUrl)) {
        setSelectedAgentId(agentIdFromUrl);
      } else if (list.length > 0) {
        setSelectedAgentId(list[0].id);
      }
    });
  }, [agentIdFromUrl]);

  const loadAgentEvaluationJobs = async (agentId: string, preferredJobId?: string) => {
    try {
      const jobs = await fetchEvaluationJobs(agentId);
      // Filter to evaluation jobs (ignore accidental execution job stubs)
      const validJobs = jobs.filter(j => !j.id.startsWith('exec-') || j.completed_scenarios > 0);
      // Sort chronologically (oldest to newest) for stable index numbering (#1, #2, etc.)
      const sorted = [...validJobs].sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
      setEvaluationJobs(sorted);

      if (sorted.length > 0) {
        const targetJob = (preferredJobId && sorted.find(j => j.id === preferredJobId)) 
          || (jobId && sorted.find(j => j.id === jobId)) 
          || sorted[sorted.length - 1];

        setSelectedJobId(targetJob.id);
        setEvalJob(targetJob);

        if (targetJob.status === 'completed' || targetJob.status === 'partial') {
          loadResults(targetJob.id);
        } else if (['pending', 'running', 'evaluating', 'aggregating'].includes(targetJob.status)) {
          setRunning(true);
          startPolling(targetJob.id);
        }
      } else {
        setSelectedJobId('');
        setEvalJob(null);
        setScorecard(null);
        setReport(null);
        setVerdicts([]);
        setTraces([]);
        setClusters([]);
      }
    } catch (e) {
      console.error('Failed to load evaluation jobs for agent:', e);
    }
  };

  useEffect(() => {
    if (selectedAgentId) {
      loadAgentEvaluationJobs(selectedAgentId, jobId);
    }
  }, [selectedAgentId]);

  const handleSelectJob = (id: string) => {
    setSelectedJobId(id);
    const target = evaluationJobs.find(j => j.id === id);
    if (target) {
      setEvalJob(target);
      if (target.status === 'completed' || target.status === 'partial') {
        loadResults(target.id);
      } else if (['pending', 'running', 'evaluating', 'aggregating'].includes(target.status)) {
        setRunning(true);
        startPolling(target.id);
      }
    }
  };

  const handleDeleteEvaluationRun = async (id: string, label: string) => {
    if (!window.confirm(`Are you sure you want to delete evaluation run '${label}'? This action cannot be undone.`)) {
      return;
    }
    try {
      await deleteEvaluationJob(id);
      const updatedJobs = evaluationJobs.filter(j => j.id !== id);
      setEvaluationJobs(updatedJobs);

      if (selectedJobId === id) {
        if (updatedJobs.length > 0) {
          const nextJob = updatedJobs[updatedJobs.length - 1];
          handleSelectJob(nextJob.id);
        } else {
          setSelectedJobId('');
          setEvalJob(null);
          setScorecard(null);
          setReport(null);
          setVerdicts([]);
          setTraces([]);
          setClusters([]);
        }
      }
    } catch (err: any) {
      alert(`Failed to delete evaluation run: ${err.message || err}`);
    }
  };

  const startPolling = (jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = window.setInterval(async () => {
      try {
        const details = await fetchEvaluationJobDetails(jobId);
        setEvalJob(details);

        if (['completed', 'failed', 'cancelled', 'partial', 'blocked'].includes(details.status)) {
          if (pollRef.current) clearInterval(pollRef.current);
          setRunning(false);

          if (details.status === 'completed' || details.status === 'partial') {
            loadResults(jobId);
            // Refresh list so latest results reflect
            if (selectedAgentId) {
              fetchEvaluationJobs(selectedAgentId).then(jList => {
                const s = [...jList].sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
                setEvaluationJobs(s);
              });
            }
          }
        }
      } catch (err) {
        console.error('Error polling evaluation job:', err);
        if (pollRef.current) clearInterval(pollRef.current);
        setRunning(false);
      }
    }, 1200);
  };

  const loadResults = async (jobId: string) => {
    try {
      setResultsError('');
      const [sc, rep, verd, trc, clus] = await Promise.all([
        fetchScorecard(jobId),
        fetchEvaluationReport(jobId),
        fetchEvaluationVerdicts(jobId),
        fetchEvaluationTracesDetails(jobId),
        fetchFailureClusters(jobId),
      ]);
      setScorecard(sc);
      setReport(rep);
      setVerdicts(verd);
      setTraces(trc);
      setClusters(clus);
    } catch (e) {
      console.error('Failed loading evaluation results:', e);
      setResultsError('Evaluation completed, but its result report could not be loaded. Retry the result request.');
    }
  };

  useEffect(() => {
    if (jobId) {
      startPolling(jobId);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [jobId]);

  const handleLaunchEvaluation = async () => {
    if (!selectedAgentId) return;
    setRunning(true);
    setScorecard(null);
    setReport(null);
    setVerdicts([]);
    setTraces([]);
    setClusters([]);
    setResultsError('');
    setUserDeclinedRepair(false);

    try {
      // Check if an execution job exists for the selected agent
      const latestExec = await fetchLatestExecutionJob(selectedAgentId).catch(() => null);
      let job: any = null;
      if (latestExec?.job?.id) {
        job = await evaluateExecutionJob(latestExec.job.id);
      } else {
        job = await runEvaluationJob(selectedAgentId, batchSize);
      }
      setEvalJob(job);
      const targetId = job?.id || job?.job_id;
      if (targetId) {
        setSelectedJobId(targetId);
        startPolling(targetId);
      } else {
        setRunning(false);
      }
    } catch (e: any) {
      console.error('Failed to launch evaluation run:', e);
      setRunning(false);
      setResultsError(e.message || 'Failed to launch evaluation run.');
    }
  };

  const selectedAgent = agents.find(a => a.id === selectedAgentId);

  const progressPct = evalJob && evalJob.total_scenarios > 0
    ? Math.round((evalJob.completed_scenarios / evalJob.total_scenarios) * 100)
    : 0;

  const isCompleted = evalJob?.status === 'completed';
  const isFailed = evalJob?.status === 'failed';
  const isEvaluating = evalJob?.status && ['pending', 'running', 'evaluating', 'aggregating'].includes(evalJob.status);
  const passedVerdicts = verdicts.filter((verdict) => verdict.passed).length;
  const failedVerdicts = verdicts.filter((verdict) => !verdict.passed).length;
  const findingCount = verdicts.reduce((total, verdict) => total + (verdict.findings?.length || 0), 0);
  const highestPriorityCluster = [...clusters].sort((a, b) => {
    const severityRank = { critical: 4, high: 3, medium: 2, low: 1 };
    return (severityRank[b.severity?.toLowerCase() as keyof typeof severityRank] || 0)
      - (severityRank[a.severity?.toLowerCase() as keyof typeof severityRank] || 0);
  })[0];
  const releaseDecision = scorecard
    ? (scorecard.total_scenarios === 0 || verdicts.length === 0)
      ? 'RELEASE BLOCKED (0 EXECUTIONS)'
      : scorecard.critical_failures > 0 || scorecard.composite < 70
      ? 'RELEASE BLOCKED'
      : scorecard.composite < 85
        ? 'REVIEW BEFORE RELEASE'
        : 'READY FOR RELEASE'
    : 'AWAITING EXECUTION';

  const renderVerdictBadge = (status?: string, passed?: boolean) => {
    const st = (status || (passed ? 'PASS' : 'FAIL')).toUpperCase();
    if (st === 'PASS') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 w-fit">
          <CheckCircle2 className="w-3 h-3" /> PASS
        </span>
      );
    }
    if (st === 'FAIL') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-950 text-rose-300 border border-rose-500/30 flex items-center gap-1 w-fit">
          <XCircle className="w-3 h-3" /> FAIL
        </span>
      );
    }
    if (st === 'BLOCKED') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-950 text-amber-300 border border-amber-500/30 flex items-center gap-1 w-fit">
          <Ban className="w-3 h-3" /> BLOCKED
        </span>
      );
    }
    if (st === 'INCONCLUSIVE' || st === 'ERROR') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-950 text-purple-300 border border-purple-500/30 flex items-center gap-1 w-fit">
          <HelpCircle className="w-3 h-3" /> {st}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700 flex items-center gap-1 w-fit">
        {st}
      </span>
    );
  };

  const renderDimScore = (val: number | null | undefined, label: string, weight: string) => {
    const isNA = val === null || val === undefined;
    return (
      <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-700/80 space-y-1">
        <span className="text-[10px] text-slate-300 block uppercase tracking-wider font-semibold">{label} ({weight})</span>
        {isNA ? (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700 inline-block font-mono">
            N/A
          </span>
        ) : (
          <span className={`font-bold text-base font-mono ${
            val >= 80 ? 'text-emerald-300' : val >= 60 ? 'text-amber-300' : 'text-rose-300'
          }`}>
            {val.toFixed(1)}%
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-5 sm:space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center space-x-2.5">
            <Zap className="w-5 h-5 sm:w-6 sm:h-6 text-cyan-400 fill-current" />
            <span>Evaluation & Failure Analysis Scorecard</span>
          </h1>
          <p className="text-xs text-slate-300 mt-1">
            Evidence-backed, 10-dimension evaluation engine analyzing execution traces, tool discipline, safety bounds, and failure clusters.
          </p>
        </div>

        {/* Launch / Select Agent Controls */}
        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <select
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="flex-1 sm:flex-none px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-cyan-300 font-mono text-xs focus:outline-none focus:border-cyan-500 transition cursor-pointer"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.display_name || a.name} · {a.version_label}
              </option>
            ))}
          </select>

          <button
            onClick={handleLaunchEvaluation}
            disabled={running || !selectedAgentId}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-cyan-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-extrabold text-xs shadow-lg shadow-cyan-500/20 flex items-center space-x-1.5 transition disabled:opacity-50 whitespace-nowrap cursor-pointer"
          >
            {running ? (
              <><RefreshCw className="w-3.5 h-3.5 animate-spin" /><span>Evaluating...</span></>
            ) : (
              <><Zap className="w-3.5 h-3.5 fill-current" /><span>Launch Evaluation</span></>
            )}
          </button>
        </div>
      </div>

      {/* ── Evaluation Run History Selector Bar (e.g., test-agent eval1, eval2, eval3) ── */}
      {evaluationJobs.length > 0 && (
        <div className="p-3.5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/80 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center space-x-2 overflow-x-auto max-w-full py-0.5">
            <span className="text-[10px] uppercase font-bold text-slate-400 font-mono shrink-0 flex items-center gap-1.5 mr-1">
              <Clock className="w-3.5 h-3.5 text-cyan-400" />
              <span>Evaluation Runs ({evaluationJobs.length}):</span>
            </span>
            {evaluationJobs.map((j, idx) => {
              const isSelected = selectedJobId === j.id;
              const isLatest = idx === evaluationJobs.length - 1;
              const evalNum = idx + 1;
              const runLabel = `${selectedAgent?.name || 'agent'} eval${evalNum}`;
              return (
                <div key={j.id} className="relative group flex items-center shrink-0">
                  <button
                    onClick={() => handleSelectJob(j.id)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-bold font-mono transition flex items-center space-x-2 cursor-pointer pr-7 ${
                      isSelected
                        ? 'bg-gradient-to-r from-cyan-600 to-indigo-600 text-white border border-cyan-400 shadow-md shadow-cyan-500/20 scale-[1.02]'
                        : 'bg-slate-900 text-slate-300 border border-slate-800 hover:border-slate-700 hover:text-white'
                    }`}
                  >
                    <span>{runLabel}</span>
                    {isLatest && (
                      <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase ${
                        isSelected ? 'bg-white/20 text-white' : 'bg-cyan-950 text-cyan-300 border border-cyan-500/30'
                      }`}>
                        Latest
                      </span>
                    )}
                    <span className={`text-[10px] ${isSelected ? 'text-cyan-100' : 'text-slate-500'}`}>
                      ({j.total_scenarios || 0} Scenarios)
                    </span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteEvaluationRun(j.id, runLabel);
                    }}
                    title={`Delete ${runLabel} run`}
                    className={`absolute right-1.5 p-1 rounded-lg transition-all cursor-pointer ${
                      isSelected
                        ? 'text-cyan-200 hover:text-rose-300 hover:bg-rose-950/60'
                        : 'text-slate-500 hover:text-rose-400 hover:bg-rose-950/60 opacity-60 group-hover:opacity-100'
                    }`}
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              );
            })}
          </div>

          <button
            onClick={handleLaunchEvaluation}
            disabled={running || !selectedAgentId}
            className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-cyan-500/40 text-cyan-300 font-bold text-xs flex items-center space-x-1.5 transition disabled:opacity-50 cursor-pointer shrink-0"
          >
            <Zap className="w-3.5 h-3.5 text-cyan-400" />
            <span>+ Re-Evaluate (eval{evaluationJobs.length + 1})</span>
          </button>
        </div>
      )}

      {/* ── Empty State when zero evaluations exist ── */}
      {evaluationJobs.length === 0 && !running && (
        <div className="p-8 sm:p-12 rounded-2xl glass-panel border border-cyan-500/30 bg-slate-950/80 text-center space-y-4 shadow-2xl animate-fadeIn">
          <div className="w-14 h-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center mx-auto">
            <Zap className="w-7 h-7 text-cyan-400 fill-current" />
          </div>
          <div className="max-w-md mx-auto space-y-1.5">
            <h3 className="text-base font-extrabold text-slate-100">
              No Evaluation Runs Yet for {selectedAgent?.display_name || selectedAgent?.name || 'this agent'}
            </h3>
            <p className="text-xs text-slate-400">
              Run dual-tier hybrid evaluation to grade execution traces against safety invariants, tool discipline, reasoning fidelity, and 10-dimension reliability scores.
            </p>
          </div>
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={handleLaunchEvaluation}
              disabled={running || !selectedAgentId}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-extrabold text-xs shadow-lg shadow-cyan-500/20 flex items-center space-x-2 transition cursor-pointer"
            >
              <Zap className="w-4 h-4 fill-current" />
              <span>Launch Evaluation (eval1)</span>
            </button>
            <button
              onClick={() => navigate(`/execution?agentId=${selectedAgentId}`)}
              className="px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-bold text-xs flex items-center space-x-2 transition cursor-pointer"
            >
              <Cpu className="w-4 h-4 text-slate-400" />
              <span>Go to Execute Scenarios →</span>
            </button>
          </div>
        </div>
      )}

      {/* Real-time Status Management & Progress Card */}
      {evalJob && (
        <div className="p-6 rounded-2xl glass-panel border border-indigo-500/30 bg-slate-950/90 space-y-4 shadow-xl font-mono">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center space-x-3">
              <div className="p-2.5 rounded-xl bg-indigo-500/20">
                <Clock className={`w-5 h-5 text-indigo-400 ${isEvaluating ? 'animate-pulse' : ''}`} />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-bold text-slate-400 uppercase">EVALUATION JOB:</span>
                  <span className="text-xs font-bold text-cyan-300">{evalJob.id}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                    isCompleted
                      ? 'bg-emerald-950 text-emerald-300 border-emerald-500/40'
                      : isFailed
                      ? 'bg-rose-950 text-rose-300 border-rose-500/40'
                      : 'bg-indigo-950 text-indigo-300 border-indigo-500/40 animate-pulse'
                  }`}>
                    ● {evalJob.status}
                  </span>
                </div>
                <p className="text-xs text-slate-300 mt-1">{evalJob.current_step || 'Processing scenarios...'}</p>
              </div>
            </div>

            <div className="text-right text-xs">
              <span className="text-slate-400">Scenarios: </span>
              <strong className="text-slate-100">{evalJob.completed_scenarios} / {evalJob.total_scenarios} ({progressPct}%)</strong>
            </div>
          </div>

          {/* Real-time Progress Bar */}
          <div className="w-full h-2.5 bg-slate-900 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-cyan-400 transition-all duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>

          {/* Failed job retry notice */}
          {isFailed && (
            <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-500/40 text-xs text-rose-200 flex items-center justify-between flex-wrap gap-2">
              <span>Failure Reason: {evalJob.error_message || 'Evaluation worker encountered an unexpected error.'}</span>
              <button
                onClick={handleLaunchEvaluation}
                className="px-3 py-1 rounded-lg bg-rose-800 hover:bg-rose-700 text-white font-bold text-[11px]"
              >
                Retry Evaluation
              </button>
            </div>
          )}
        </div>
      )}

      {resultsError && (
        <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-sm text-rose-200 flex items-center justify-between gap-4">
          <span>{resultsError}</span>
          {evalJob?.id && <button onClick={() => loadResults(evalJob.id)} className="shrink-0 px-3 py-1.5 rounded-lg bg-rose-800 hover:bg-rose-700 text-xs font-bold">Retry Results</button>}
        </div>
      )}

      {isCompleted && !scorecard && !resultsError && (
        <div className="p-4 rounded-2xl bg-amber-950/30 border border-amber-500/30 text-sm text-amber-200">
          Evaluation finished. Loading the scorecard and scenario evidence...
        </div>
      )}

      {scorecard && (
        <section className="p-5 rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/30 via-slate-950 to-indigo-950/30 space-y-4">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-cyan-300">Evaluation decision snapshot</p>
              <h2 className="text-xl font-extrabold text-slate-100 mt-1">{scorecard.agent_name}</h2>
              <p className="text-xs text-slate-400 mt-1">{scorecard.agent_version} · {scorecard.total_scenarios} scenarios · evidence-backed result</p>
            </div>
            <span className={`px-3 py-1.5 rounded-lg border text-xs font-mono font-extrabold ${
              releaseDecision === 'READY FOR RELEASE'
                ? 'bg-emerald-950 text-emerald-300 border-emerald-500/40'
                : releaseDecision === 'REVIEW BEFORE RELEASE'
                  ? 'bg-amber-950 text-amber-300 border-amber-500/40'
                  : 'bg-rose-950 text-rose-300 border-rose-500/40'
            }`}>{releaseDecision}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 font-mono">
            <div className="p-3 rounded-xl bg-slate-950/80 border border-cyan-500/20">
              <p className="text-[10px] text-slate-500 uppercase">Reliability Score</p>
              <p className="text-2xl font-bold text-cyan-300">
                {verdicts.length > 0 ? scorecard.composite.toFixed(1) : '—'}
                <span className="text-xs text-slate-500"> / 100</span>
              </p>
            </div>
            <div className="p-3 rounded-xl bg-slate-950/80 border border-indigo-500/20">
              <p className="text-[10px] text-slate-500 uppercase">Design Coverage</p>
              <p className="text-2xl font-bold text-indigo-300">
                {scorecard.total_scenarios}
                <span className="text-xs text-slate-500"> designed</span>
              </p>
            </div>
            <div className="p-3 rounded-xl bg-slate-950/80 border border-purple-500/20">
              <p className="text-[10px] text-slate-500 uppercase">Execution Coverage</p>
              <p className="text-2xl font-bold text-purple-300">
                {traces.length}
                <span className="text-xs text-slate-500"> / {scorecard.total_scenarios} ({Math.round((traces.length / Math.max(1, scorecard.total_scenarios)) * 100)}%)</span>
              </p>
            </div>
            <div className="p-3 rounded-xl bg-slate-950/80 border border-emerald-500/20">
              <p className="text-[10px] text-slate-500 uppercase">Evaluation Coverage</p>
              <p className="text-2xl font-bold text-emerald-300">
                {verdicts.length}
                <span className="text-xs text-slate-500"> / {scorecard.total_scenarios} ({Math.round((verdicts.length / Math.max(1, scorecard.total_scenarios)) * 100)}%)</span>
              </p>
            </div>
            <div className="p-3 rounded-xl bg-slate-950/80 border border-rose-500/20">
              <p className="text-[10px] text-slate-500 uppercase">Failures / Findings</p>
              <p className="text-2xl font-bold text-rose-300">
                {failedVerdicts} <span className="text-xs text-amber-400 font-bold">({findingCount} findings)</span>
              </p>
            </div>
          </div>
          {highestPriorityCluster ? (
            <div className="p-3 rounded-xl bg-rose-950/30 border border-rose-500/25 text-xs">
              <p className="font-bold text-rose-200">Highest-priority issue: {highestPriorityCluster.title || highestPriorityCluster.label}</p>
              <p className="text-slate-300 mt-1">{highestPriorityCluster.root_cause_pattern || highestPriorityCluster.representative_evidence}</p>
              <p className="text-emerald-300 mt-1"><span className="font-bold">Recommended fix:</span> {highestPriorityCluster.recommended_fix || highestPriorityCluster.remediation_suggestion}</p>
            </div>
          ) : (
            <p className="text-xs text-emerald-300">No failure cluster was reported. Review individual scenario evidence below before release.</p>
          )}
        </section>
      )}

      {/* SECTION A: Evaluation Overview Dashboard */}
      {scorecard && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 font-mono">
            {/* Overall Score */}
            <div className="p-6 rounded-2xl glass-panel border border-cyan-500/30 bg-gradient-to-tr from-cyan-950/30 via-slate-950 to-slate-950 space-y-2">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">OVERALL RELIABILITY SCORE</span>
              <div className="flex items-baseline space-x-2">
                <span className="text-4xl font-extrabold text-cyan-400">{scorecard.composite.toFixed(1)}</span>
                <span className="text-sm text-slate-500">/ 100</span>
              </div>
              <p className="text-[11px] text-slate-400">Formula: {scorecard.score_formula_version || 'v2.0-weighted'}</p>
            </div>

            {/* Confidence & Fidelity */}
            <div className="p-6 rounded-2xl glass-panel border border-indigo-500/30 bg-slate-950 space-y-2">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">EVALUATION CONFIDENCE</span>
              <div className="text-2xl font-extrabold text-indigo-400">{scorecard.confidence || 'HIGH'}</div>
              <p className="text-[11px] text-slate-400">Two-Layer: Deterministic + LLM Judge</p>
            </div>

            {/* Scenario Breakdown */}
            <div className="p-6 rounded-2xl glass-panel border border-emerald-500/30 bg-slate-950 space-y-2">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">PASSED SCENARIOS</span>
              <div className="text-2xl font-extrabold text-emerald-400">
                {scorecard.passed} <span className="text-sm text-slate-500 font-normal">/ {scorecard.total_scenarios}</span>
              </div>
              <p className="text-[11px] text-slate-400">{((scorecard.passed / Math.max(1, scorecard.total_scenarios)) * 100).toFixed(1)}% Pass Rate</p>
            </div>

            {/* Critical Failures */}
            <div className="p-6 rounded-2xl glass-panel border border-rose-500/30 bg-slate-950 space-y-2">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">CRITICAL FAILURES</span>
              <div className="text-2xl font-extrabold text-rose-400">{scorecard.critical_failures}</div>
              <p className="text-[11px] text-slate-400">Policy violations & uncontained side effects</p>
            </div>
          </div>

          {/* SECTION D: Explainable Report Rationale */}
          {report && report.explainability && (
            <div className="p-6 rounded-2xl glass-panel border border-indigo-500/20 bg-slate-950 space-y-3 font-mono">
              <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider flex items-center gap-2">
                <Info className="w-4 h-4 text-indigo-400" />
                Explainable Evidence & Evaluation Rationale
              </h3>
              <div className="space-y-2 text-xs">
                {report.explainability.map((line: string, idx: number) => (
                  <div key={idx} className="p-3 rounded-xl bg-slate-900/80 border border-slate-850 text-slate-300">
                    {line}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* SECTION F: Failure Clusters Integration */}
          {clusters.length > 0 && <FailureClustersView clusters={clusters} />}

          {/* SECTION G: Evaluation -> Fix My Agent Integration Banner */}
          <div className="p-6 rounded-2xl glass-panel border border-rose-500/40 bg-gradient-to-r from-rose-950/30 via-slate-950 to-slate-950 space-y-4 shadow-xl">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="space-y-1">
                <h3 className="text-base font-extrabold text-slate-100 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-rose-400" />
                  <span>Issues Detected — Repair Recommendation</span>
                </h3>
                <div className="flex items-center space-x-4 text-xs font-mono">
                  <span className="text-rose-400 font-bold">❌ {scorecard.failed} test cases failed</span>
                  <span className="text-amber-400 font-bold">⚠️ {scorecard.critical_failures} critical reliability issues</span>
                </div>
                <p className="text-xs text-slate-300 font-semibold mt-1">
                  Would you like Fix My Agent to attempt autonomous repairs based on this evaluation report?
                </p>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setUserDeclinedRepair(true)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-300 transition"
                >
                  Not Now
                </button>
                <button
                  onClick={() => navigate("/fix-agent")}
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-rose-500 via-indigo-600 to-cyan-500 hover:from-rose-400 hover:to-cyan-400 text-white font-extrabold text-xs shadow-lg shadow-rose-500/25 flex items-center space-x-2 transition hover:scale-[1.02]"
                >
                  <Wrench className="w-4 h-4" />
                  <span>Fix Agent</span>
                </button>
              </div>
            </div>

            {userDeclinedRepair && (
              <div className="p-3 rounded-xl bg-slate-900 border border-slate-850 text-xs text-slate-400 font-mono">
                Review mode active. Agent configuration remains unchanged. You can navigate to 'Fix My Agent' anytime.
              </div>
            )}
          </div>

          {/* SECTION B: Model Binding & Fidelity Banner */}
          <div className="p-5 rounded-2xl glass-panel border border-amber-500/30 bg-amber-950/20 flex items-center justify-between flex-wrap gap-4 font-mono">
            <div className="flex items-center space-x-3">
              <Cpu className="w-5 h-5 text-amber-400" />
              <div>
                <div className="flex items-center space-x-2 text-xs">
                  <span className="font-bold text-slate-100 uppercase">MODE: {scorecard.execution_mode.toUpperCase()}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    Substitution: {scorecard.model_substitution ? 'YES' : 'NO'}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                    Fidelity: {scorecard.confidence || 'HIGH'}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Evaluated on immutable sandbox execution traces
                </p>
              </div>
            </div>
            <div className="text-right text-[11px] text-slate-400">
              <span>Formula Version: </span>
              <strong className="text-cyan-400">{scorecard.score_formula_version || 'v2.0-weighted'}</strong>
            </div>
          </div>

          <TwoAxisQuadrant scorecard={scorecard} />

          {/* SECTION C: 10-Dimension Score Breakdown */}
          {scorecard.dimension_scores && (
            <div className="p-6 rounded-2xl glass-panel border border-slate-800 bg-slate-950 space-y-4">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-cyan-400" />
                10-Dimension Reliability Scorecard
              </h3>

              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 font-mono text-xs">
                {renderDimScore(scorecard.dimension_scores.correctness, 'CORRECTNESS', '25%')}
                {renderDimScore(scorecard.dimension_scores.goal_adherence, 'GOAL ADHERENCE', '15%')}
                {renderDimScore(scorecard.dimension_scores.safety, 'SAFETY', '15%')}
                {renderDimScore(scorecard.dimension_scores.security, 'SECURITY', '10%')}
                {renderDimScore(scorecard.dimension_scores.tool_discipline, 'TOOL DISCIPLINE', '10%')}
                {renderDimScore(scorecard.dimension_scores.robustness, 'ROBUSTNESS', '5%')}
                {renderDimScore(scorecard.dimension_scores.recovery, 'RECOVERY', '5%')}
                {renderDimScore(scorecard.dimension_scores.output_quality, 'OUTPUT QUALITY', '5%')}
                {renderDimScore(scorecard.dimension_scores.efficiency, 'EFFICIENCY', '5%')}
                {renderDimScore(scorecard.dimension_scores.compliance, 'COMPLIANCE', '5%')}
              </div>
            </div>
          )}

          {/* SECTION E: Scenario Results Table with Expandable Evidence */}
          {verdicts.length > 0 && (
            <div className="p-6 rounded-2xl glass-panel border border-slate-800 bg-slate-950 space-y-4 font-mono">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center justify-between">
                <span>Scenario Verdicts & Trace Evidence ({verdicts.length} Evaluated)</span>
                <span className="text-slate-500 text-[10px]">Click row to inspect trace</span>
              </h3>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-500 text-[10px] uppercase">
                      <th className="py-2.5 px-3">SCENARIO ID</th>
                      <th className="py-2.5 px-3">VERDICT</th>
                      <th className="py-2.5 px-3">SCORE</th>
                      <th className="py-2.5 px-3">FINDINGS</th>
                      <th className="py-2.5 px-3">METHOD</th>
                      <th className="py-2.5 px-3 text-right">ACTION</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-900">
                    {verdicts.map((v) => {
                      const isExpanded = expandedScenarioId === v.scenario_id;
                      const trace = traces.find((t) => t.scenario_id === v.scenario_id);
                      return (
                        <React.Fragment key={v.scenario_id}>
                          <tr
                            onClick={() => setExpandedScenarioId(isExpanded ? null : v.scenario_id)}
                            className="hover:bg-slate-900/60 cursor-pointer transition"
                          >
                            <td className="py-3 px-3 font-bold text-cyan-300">{v.scenario_id}</td>
                            <td className="py-3 px-3">
                              {renderVerdictBadge(v.status, v.passed)}
                            </td>
                            <td className="py-3 px-3 font-bold text-slate-200">
                              {v.final_score !== undefined ? `${v.final_score}%` : '100%'}
                            </td>
                            <td className="py-3 px-3 text-slate-300">
                              {v.findings?.length || 0} Findings
                            </td>
                            <td className="py-3 px-3 text-[11px] text-indigo-300">
                              {v.evaluation_method || 'DETERMINISTIC'}
                            </td>
                            <td className="py-3 px-3 text-right text-slate-400">
                              {isExpanded ? <ChevronDown className="w-4 h-4 inline" /> : <ChevronRight className="w-4 h-4 inline" />}
                            </td>
                          </tr>

                          {/* Expanded Evidence View */}
                          {isExpanded && (
                            <tr>
                              <td colSpan={6} className="p-4 bg-slate-900/90 border-b border-slate-800 space-y-3">
                                <div className="space-y-2">
                                  <p className="text-[10px] text-cyan-400 font-bold uppercase">Verdict Findings & Evidence:</p>
                                  {v.findings && v.findings.length > 0 ? (
                                    v.findings.map((f: any, fidx: number) => (
                                      <div key={fidx} className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                                        <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
                                          <span className="font-bold text-rose-300">[{f.category}] {f.title || f.category}</span>
                                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-rose-950 text-rose-300 border border-rose-500/30">
                                            {f.severity}
                                          </span>
                                        </div>
                                        <p className="text-[11px] text-slate-300">{f.description || f.explanation}</p>
                                        <div className="grid grid-cols-2 gap-2 text-[10px] text-slate-400 bg-slate-900 p-2 rounded">
                                          <div><strong>Expected:</strong> {f.expected || 'N/A'}</div>
                                          <div><strong>Observed:</strong> {f.observed || 'N/A'}</div>
                                        </div>
                                        {f.remediation && (
                                          <p className="text-[11px] text-emerald-300">💡 <strong>Remediation:</strong> {f.remediation}</p>
                                        )}
                                      </div>
                                    ))
                                  ) : (
                                    <p className="text-emerald-400 text-[11px]">Scenario passed all deterministic assertions and semantic rules cleanly.</p>
                                  )}
                                </div>

                                {trace && trace.events && (
                                  <div className="space-y-1">
                                    <p className="text-[10px] text-slate-500 font-bold uppercase">Execution Trace Events:</p>
                                    <div className="p-3 rounded bg-slate-950 border border-slate-850 text-[10px] space-y-1 max-h-48 overflow-y-auto">
                                      {trace.events.map((e: any, eidx: number) => (
                                        <div key={eidx} className="flex space-x-2">
                                          <span className="text-indigo-400 font-bold">[{e.role}]:</span>
                                          <span className="text-slate-300">{e.content}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Engine 6 Transition Banner */}
      {isCompleted && (
        <div className="p-4 sm:p-5 rounded-2xl glass-panel border border-cyan-500/40 bg-gradient-to-r from-slate-950 via-cyan-950/20 to-slate-950 flex items-center justify-between flex-wrap gap-4 shadow-xl">
          <div className="space-y-1">
            <h3 className="text-sm font-extrabold text-cyan-300 flex items-center gap-2">
              <Wrench className="w-4 h-4 text-cyan-400" />
              <span>Step 6: Automated Remediation & Self-Healing</span>
            </h3>
            <p className="text-xs text-slate-300">
              Generate AST-level code patches, hardened system prompts, and verify score improvements for identified failure clusters.
            </p>
          </div>
          <button
            onClick={() => navigate(`/fix-agent?agentId=${selectedAgentId}&jobId=${evalJob?.id}`)}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-rose-600 hover:from-cyan-400 hover:to-rose-500 text-white font-extrabold text-xs shadow-lg shadow-cyan-500/25 flex items-center space-x-2 transition"
          >
            <span>Proceed to 6. Fix My Agent</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Process Activity Log */}
      <LiveProcessMonitor />
    </div>
  );
};
