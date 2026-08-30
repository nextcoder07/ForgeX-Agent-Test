import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Bug, Wrench, GitCompare, Database, Zap, ShieldAlert, ArrowRight, CheckCircle2, AlertTriangle, Info, RefreshCw } from 'lucide-react';
import { DiagnosisPage } from './DiagnosisPage';
import { FixMyAgentPage } from './FixMyAgentPage';
import { RegressionPage } from './RegressionPage';
import { TrainingDatasetPage } from './TrainingDatasetPage';
import { fetchAgents, fetchExecutionJobs, fetchImproveSummary } from '../api/client';
import type { AgentRecord, ExecutionJob, ImproveSummary } from '../api/client';

export const ImprovePage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = (searchParams.get('tab') || 'failures') as 'failures' | 'repairs' | 'regression' | 'training';

  const agentIdFromUrl = searchParams.get('agentId') || '';
  const jobIdFromUrl = searchParams.get('jobId') || '';

  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>(agentIdFromUrl);
  const [evaluationJobs, setEvaluationJobs] = useState<ExecutionJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>(jobIdFromUrl);
  const [improveSummary, setImproveSummary] = useState<ImproveSummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  useEffect(() => {
    Promise.all([fetchAgents(), fetchExecutionJobs()])
      .then(([agentList, jobs]) => {
        setAgents(agentList);
        setEvaluationJobs(jobs);
        if (!selectedAgentId && agentList.length > 0) {
          const defaultId = agentList[0].id;
          setSelectedAgentId(defaultId);
          setSearchParams(prev => {
            const next = new URLSearchParams(prev);
            if (!next.has('agentId')) next.set('agentId', defaultId);
            return next;
          });
        }
      })
      .catch(err => console.error('Error fetching header summary data:', err));
  }, []);

  useEffect(() => {
    if (!selectedAgentId) return;
    setLoadingSummary(true);
    fetchImproveSummary(selectedAgentId, selectedJobId || undefined)
      .then(summary => setImproveSummary(summary))
      .catch(() => setImproveSummary(null))
      .finally(() => setLoadingSummary(false));
  }, [selectedAgentId, selectedJobId]);

  const handleAgentChange = (agentId: string) => {
    setSelectedAgentId(agentId);
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (agentId) next.set('agentId', agentId);
      else next.delete('agentId');
      return next;
    });
  };

  const handleRunChange = (runId: string) => {
    setSelectedJobId(runId);
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (runId) next.set('jobId', runId);
      else next.delete('jobId');
      return next;
    });
  };

  const tabs = [
    { id: 'failures' as const, label: 'Failures & Diagnosis', icon: Bug },
    { id: 'repairs' as const, label: 'Repairs & Self-Healing', icon: Wrench },
    { id: 'regression' as const, label: 'Regression', icon: GitCompare },
    { id: 'training' as const, label: 'Model Training', icon: Database },
  ];

  const selectedAgent = agents.find(a => a.id === selectedAgentId);
  const agentJobs = evaluationJobs.filter(j => j.agent_id === selectedAgentId || (selectedAgent && j.agent_name === selectedAgent.name));

  const totalFailures = improveSummary?.total_failures ?? 0;
  const criticalFailures = improveSummary?.critical_failures ?? 0;
  const repairableIssues = improveSummary?.repairable_issues ?? 0;
  const fidelity = improveSummary?.evaluation_fidelity ?? 0;

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-5">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-slate-950/60 p-4 rounded-2xl border border-slate-800/80 shadow-md">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-cyan-950/70 border border-cyan-500/30 text-cyan-400">
            <Wrench className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg sm:text-xl font-extrabold text-slate-100 tracking-tight">Improve Agent</h1>
              <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded-md bg-cyan-950 text-cyan-300 border border-cyan-500/30">
                ACTION LAYER
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Automated root-cause diagnosis, self-healing repairs, regression testing & dataset export
            </p>
          </div>
        </div>

        {/* Global Agent & Evaluation Selector */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center space-x-2 bg-slate-900/90 px-3 py-1.5 rounded-xl border border-slate-800">
            <span className="text-[11px] font-mono text-slate-400 font-medium">Agent:</span>
            <select
              value={selectedAgentId}
              onChange={(e) => handleAgentChange(e.target.value)}
              className="bg-transparent border-none text-xs font-mono font-bold text-cyan-300 focus:outline-none cursor-pointer"
            >
              {agents.length === 0 && <option value="" className="bg-slate-900">[ Select agent ]</option>}
              {agents.map((a) => (
                <option key={a.id} value={a.id} className="bg-slate-900 text-slate-200">
                  {a.display_name || a.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-2 bg-slate-900/90 px-3 py-1.5 rounded-xl border border-slate-800">
            <span className="text-[11px] font-mono text-slate-400 font-medium">Run:</span>
            <select
              value={selectedJobId}
              onChange={(e) => handleRunChange(e.target.value)}
              className="bg-transparent border-none text-xs font-mono text-slate-200 focus:outline-none cursor-pointer max-w-[200px] truncate"
            >
              <option value="" className="bg-slate-900">Latest Run</option>
              {agentJobs.map((j) => (
                <option key={j.id} value={j.id} className="bg-slate-900 text-slate-200">
                  {j.id} ({j.completed_scenarios}/{j.total_scenarios})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* STATUS BANNER */}
      {improveSummary?.status === 'NO_EVALUATION_AVAILABLE' && (
        <div className="p-4 rounded-2xl bg-amber-950/30 border border-amber-500/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-amber-200 font-mono text-xs shadow-lg">
          <div className="flex items-center space-x-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <span className="font-extrabold text-amber-300">NO EVALUATION AVAILABLE</span>
              <p className="text-[11px] text-amber-200/80 mt-0.5">
                Run an evaluation in Sandbox before using the Improve Action Layer.
              </p>
            </div>
          </div>
          <button
            onClick={() => navigate(`/executions${selectedAgentId ? `?agentId=${selectedAgentId}` : ''}`)}
            className="px-3.5 py-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-500/40 font-bold transition cursor-pointer shrink-0"
          >
            Go to Execution Sandbox →
          </button>
        </div>
      )}

      {improveSummary?.status === 'NO_FAILURES_DETECTED' && (
        <div className="p-4 rounded-2xl bg-emerald-950/30 border border-emerald-500/30 flex items-center justify-between text-emerald-200 font-mono text-xs shadow-lg">
          <div className="flex items-center space-x-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <span className="font-extrabold text-emerald-300">✓ ALL SCENARIOS PASSED CLEANLY</span>
              <p className="text-[11px] text-emerald-200/80 mt-0.5">
                All {improveSummary.scenarios_evaluated} evaluated scenarios satisfied their deterministic & safety assertions cleanly.
              </p>
            </div>
          </div>
          <span className="px-3 py-1 rounded-lg bg-emerald-900/60 border border-emerald-700/50 text-[10px] text-emerald-300 font-bold">
            100% PASS RATE
          </span>
        </div>
      )}

      {/* IMPROVEMENT SUMMARY KPI GRID */}
      <div className="p-4 sm:p-5 rounded-2xl border border-slate-800 bg-slate-950/80 space-y-4 font-mono shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              EVIDENCE SUMMARY — {selectedAgent ? selectedAgent.name : 'Target Agent'}
            </h2>
          </div>
          <button
            onClick={() => navigate(`/results${selectedAgentId ? `?agentId=${selectedAgentId}` : ''}`)}
            className="px-3 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-cyan-300 text-[11px] font-bold border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer"
          >
            <span>Evaluation Results</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1">
            <span className="text-[10px] uppercase text-slate-400 font-bold">Total Failures</span>
            <div className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
              <span>{totalFailures}</span>
              {totalFailures > 0 && <span className="w-2 h-2 rounded-full bg-rose-400 animate-pulse" />}
            </div>
            <span className="text-[10px] text-slate-500">Assertion violations</span>
          </div>

          <div className="p-3.5 rounded-xl bg-rose-950/20 border border-rose-900/40 space-y-1">
            <span className="text-[10px] uppercase text-rose-400 font-bold">Critical Failures</span>
            <div className="text-2xl font-extrabold text-rose-300">{criticalFailures}</div>
            <span className="text-[10px] text-rose-400/80">Safety & vulnerability</span>
          </div>

          <div className="p-3.5 rounded-xl bg-cyan-950/20 border border-cyan-900/40 space-y-1">
            <span className="text-[10px] uppercase text-cyan-400 font-bold">Repairable Issues</span>
            <div className="text-2xl font-extrabold text-cyan-300">{repairableIssues}</div>
            <span className="text-[10px] text-cyan-400/80">Code & prompt patches</span>
          </div>

          <div className="p-3.5 rounded-xl bg-indigo-950/20 border border-indigo-900/40 space-y-1">
            <span className="text-[10px] uppercase text-indigo-400 font-bold">Evidence Fidelity</span>
            <div className="text-2xl font-extrabold text-indigo-300">
              {improveSummary ? `${fidelity}%` : 'N/A'}
            </div>
            <span className="text-[10px] text-indigo-400/80">Trace grounded</span>
          </div>
        </div>

        {/* Detailed Scenario Breakdown Pills */}
        {improveSummary && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-900 text-[11px]">
            <span className="text-slate-400 font-bold uppercase text-[10px]">Scenarios:</span>
            <span className="px-2.5 py-0.5 rounded-md bg-slate-900 text-slate-200 border border-slate-800 font-mono">
              Total: <strong>{improveSummary.scenarios_evaluated}</strong>
            </span>
            <span className="px-2.5 py-0.5 rounded-md bg-emerald-950/50 text-emerald-300 border border-emerald-800/40 font-mono">
              Passed: <strong>{improveSummary.passed}</strong>
            </span>
            <span className="px-2.5 py-0.5 rounded-md bg-rose-950/50 text-rose-300 border border-rose-800/40 font-mono">
              Failed: <strong>{improveSummary.failed}</strong>
            </span>
            <span className="px-2.5 py-0.5 rounded-md bg-slate-900 text-slate-400 border border-slate-800 font-mono">
              Inconclusive: <strong>{improveSummary.inconclusive}</strong>
            </span>
          </div>
        )}
      </div>

      {/* Responsive Scrollable Tab Bar */}
      <div className="flex items-center space-x-1 border-b border-slate-800 overflow-x-auto no-scrollbar pb-0.5">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setSearchParams({ tab: t.id, agentId: selectedAgentId, jobId: selectedJobId })}
            className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-bold rounded-t-xl border-b-2 transition-all cursor-pointer whitespace-nowrap shrink-0 ${
              tab === t.id
                ? 'border-cyan-400 text-cyan-300 bg-slate-900/90 shadow-sm'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
            }`}
          >
            <t.icon className="w-3.5 h-3.5" />
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="pt-1">
        {tab === 'failures' && <DiagnosisPage />}
        {tab === 'repairs' && <FixMyAgentPage />}
        {tab === 'regression' && <RegressionPage />}
        {tab === 'training' && <TrainingDatasetPage />}
      </div>
    </div>
  );
};

