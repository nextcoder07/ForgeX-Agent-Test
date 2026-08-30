/**
 * ImprovePage — Stage 6
 * Consolidates: Diagnosis (Failures), Fix Agent (Repairs), Regression, Training Datasets
 * Maps legacy routes: /diagnosis, /fix-agent, /regression, /training
 */
import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Bug, Wrench, GitCompare, Database, Zap, ShieldAlert, ArrowRight, RefreshCw, Cpu, Layers } from 'lucide-react';
import { DiagnosisPage } from './DiagnosisPage';
import { FixMyAgentPage } from './FixMyAgentPage';
import { RegressionPage } from './RegressionPage';
import { TrainingDatasetPage } from './TrainingDatasetPage';
import { fetchAgents, fetchExecutionJobs, fetchAgentDiagnosisReport } from '../api/client';
import type { AgentRecord, ExecutionJob, AgentDiagnosisReport } from '../api/client';

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
  const [diagReport, setDiagReport] = useState<AgentDiagnosisReport | null>(null);
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
    fetchAgentDiagnosisReport(selectedAgentId)
      .then(report => setDiagReport(report))
      .catch(() => setDiagReport(null))
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

  const totalFailures = diagReport?.total_failures ?? 0;
  const criticalFailures = diagReport?.critical_failures ?? 0;
  const repairableIssues = diagReport?.diagnoses?.length ?? 0;

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-5">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center space-x-2.5">
            <Wrench className="w-5 h-5 sm:w-6 sm:h-6 text-cyan-400" />
            <span>Improve</span>
            <span className="px-2 py-0.5 text-xs font-mono rounded bg-cyan-950 text-cyan-300 border border-cyan-500/30">
              EVIDENCE-DRIVEN ACTION LAYER
            </span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Execution → Evaluation → Findings → Diagnosis → Repair → Regression → Training
          </p>
        </div>

        {/* Global Agent & Evaluation Selector */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-2 bg-slate-900/80 p-1.5 rounded-xl border border-slate-800">
            <label className="text-xs font-mono text-slate-400 pl-1">Agent:</label>
            <select
              value={selectedAgentId}
              onChange={(e) => handleAgentChange(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1 text-xs font-mono font-bold text-cyan-300 focus:outline-none focus:border-cyan-500 cursor-pointer"
            >
              {agents.length === 0 && <option value="">[ Select an agent ▼ ]</option>}
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name || a.name} ({a.id})
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-2 bg-slate-900/80 p-1.5 rounded-xl border border-slate-800">
            <label className="text-xs font-mono text-slate-400 pl-1">Evaluation Run:</label>
            <select
              value={selectedJobId}
              onChange={(e) => handleRunChange(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500 cursor-pointer max-w-[280px] truncate"
            >
              <option value="">Latest Evaluation Run</option>
              {agentJobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.id} · {j.completed_scenarios}/{j.total_scenarios} tests
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* IMPROVEMENT SUMMARY Top Bar */}
      <div className="p-4 sm:p-5 rounded-2xl glass-panel border border-cyan-500/20 bg-slate-950/80 space-y-3 font-mono shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              IMPROVEMENT SUMMARY — {selectedAgent ? selectedAgent.name : 'Target Agent'}
            </h3>
          </div>
          <button
            onClick={() => navigate(`/results${selectedAgentId ? `?agentId=${selectedAgentId}` : ''}`)}
            className="px-3 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-cyan-300 text-[11px] font-bold border border-slate-700 flex items-center space-x-1.5 transition cursor-pointer"
          >
            <span>[ Open Evaluation Results ]</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
            <span className="text-[10px] uppercase text-slate-400">Total Failures</span>
            <div className="text-xl font-extrabold text-slate-100 flex items-center gap-1.5">
              <span>{totalFailures}</span>
              {totalFailures > 0 && <span className="w-2 h-2 rounded-full bg-rose-400 animate-pulse" />}
            </div>
            <span className="text-[9px] text-slate-500">Assertion violations</span>
          </div>

          <div className="p-3 rounded-xl bg-rose-950/20 border border-rose-900/40 space-y-1">
            <span className="text-[10px] uppercase text-rose-400">Critical Failures</span>
            <div className="text-xl font-extrabold text-rose-300">{criticalFailures}</div>
            <span className="text-[9px] text-rose-400/80">Safety & vulnerability</span>
          </div>

          <div className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-900/40 space-y-1">
            <span className="text-[10px] uppercase text-cyan-400">Repairable Issues</span>
            <div className="text-xl font-extrabold text-cyan-300">{repairableIssues}</div>
            <span className="text-[9px] text-cyan-400/80">Patchable code & prompt</span>
          </div>

          <div className="p-3 rounded-xl bg-indigo-950/20 border border-indigo-900/40 space-y-1">
            <span className="text-[10px] uppercase text-indigo-400">Evaluation Fidelity</span>
            <div className="text-xl font-extrabold text-indigo-300">
              {diagReport ? `${Math.round(100 - (totalFailures * 5))}%` : 'N/A'}
            </div>
            <span className="text-[9px] text-indigo-400/80">Evidence-grounded</span>
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex items-center space-x-1 border-b border-slate-800 flex-wrap">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setSearchParams({ tab: t.id, agentId: selectedAgentId, jobId: selectedJobId })}
            className={`flex items-center space-x-1.5 px-4 py-2.5 text-xs font-bold rounded-t-xl border-b-2 transition-all cursor-pointer ${
              tab === t.id
                ? 'border-cyan-400 text-cyan-300 bg-slate-900/80'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
            }`}
          >
            <t.icon className="w-3.5 h-3.5" />
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'failures' && <DiagnosisPage />}
      {tab === 'repairs' && <FixMyAgentPage />}
      {tab === 'regression' && <RegressionPage />}
      {tab === 'training' && <TrainingDatasetPage />}
    </div>
  );
};

