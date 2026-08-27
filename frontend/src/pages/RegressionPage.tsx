import React, { useState, useEffect } from 'react';
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { compareRegressions, fetchAgents, fetchExecutionJobs } from '../api/client';
import type { RegressionComparison, AgentRecord, ExecutionJob } from '../api/client';
import { RegressionView } from '../components/RegressionView';
import { PipelineSequenceTracker } from '../components/PipelineSequenceTracker';
import { GitCompare, RefreshCw, AlertTriangle, ArrowRight, ShieldCheck } from 'lucide-react';

export const RegressionPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const agentIdFromUrl = queryParams.get('agentId');

  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>(agentIdFromUrl || '');
  const [jobs, setJobs] = useState<ExecutionJob[]>([]);
  const [fromJobId, setFromJobId] = useState('');
  const [toJobId, setToJobId] = useState('');
  const [comparison, setComparison] = useState<RegressionComparison | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    Promise.all([fetchAgents(), fetchExecutionJobs()])
      .then(([agentList, jobList]) => {
        setAgents(agentList);
        setJobs(jobList);
        if (!selectedAgentId && agentList.length > 0) {
          setSelectedAgentId(agentList[0].id);
        }
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedAgentId) return;
    const agentJobs = jobs.filter(j => j.agent_id === selectedAgentId || j.agent_name?.toLowerCase().includes(selectedAgentId.toLowerCase()));
    if (agentJobs.length >= 2) {
      setFromJobId(agentJobs[0].id);
      setToJobId(agentJobs[1].id);
    } else if (agentJobs.length === 1) {
      setFromJobId(agentJobs[0].id);
      setToJobId('');
    } else if (jobs.length >= 2) {
      setFromJobId(jobs[0].id);
      setToJobId(jobs[1].id);
    }
  }, [selectedAgentId, jobs]);

  const handleCompare = async () => {
    if (!fromJobId || !toJobId) return;
    setLoading(true);
    setComparison(null);
    try {
      const result = await compareRegressions(fromJobId, toJobId);
      setComparison(result);
    } catch (e) {
      console.error('Failed to compare regression versions:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (fromJobId && toJobId) {
      handleCompare();
    }
  }, [fromJobId, toJobId]);

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center gap-2">
          <GitCompare className="w-5 h-5 text-indigo-400" />
          <span>Regression & Version Diff Engine</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-300 mt-1">
          Compare two evaluation runs to detect regressions before deploying agent updates. Proves safety/capability deltas and validates resolved vulnerabilities.
        </p>
      </div>

      {/* Comparison Controls */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 flex flex-wrap items-end gap-4 font-mono">
        <div>
          <label className="text-xs font-semibold text-slate-400 block mb-1">Target Agent:</label>
          <select
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="p-2.5 rounded-xl bg-slate-900 border border-slate-700 text-cyan-300 text-xs focus:outline-none focus:border-indigo-500 transition min-w-[200px]"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.display_name || a.name} · {a.version_label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-400 block mb-1">Baseline Run (v1.0):</label>
          <select
            value={fromJobId}
            onChange={(e) => setFromJobId(e.target.value)}
            className="p-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-200 text-xs focus:outline-none focus:border-indigo-500 transition min-w-[200px]"
          >
            <option value="">-- Select Baseline Run --</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.id.slice(0, 16)} ({j.agent_name || 'Run'})
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-end pb-2">
          <GitCompare className="w-5 h-5 text-indigo-400" />
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-400 block mb-1">Candidate Run (v1.1 / Repaired):</label>
          <select
            value={toJobId}
            onChange={(e) => setToJobId(e.target.value)}
            className="p-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-200 text-xs focus:outline-none focus:border-indigo-500 transition min-w-[200px]"
          >
            <option value="">-- Select Candidate Run --</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.id.slice(0, 16)} ({j.agent_name || 'Run'})
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={handleCompare}
          disabled={loading || !fromJobId || !toJobId}
          className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 hover:from-indigo-400 hover:to-violet-500 text-slate-100 font-bold text-xs shadow-lg shadow-indigo-500/20 flex items-center space-x-2 transition disabled:opacity-50 cursor-pointer"
        >
          {loading ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Comparing Runs...</span>
            </>
          ) : (
            <>
              <GitCompare className="w-4 h-4" />
              <span>Compare Versions</span>
            </>
          )}
        </button>
      </div>

      {/* Comparison Result */}
      {comparison && <RegressionView comparison={comparison} />}

      {!comparison && !loading && (
        <div className="py-12 text-center space-y-3 rounded-2xl border border-slate-800 bg-slate-900/40 p-6 font-mono">
          <GitCompare className="w-10 h-10 mx-auto text-slate-600" />
          <p className="text-sm font-bold text-slate-300">Select two completed evaluation runs to generate a comparative regression diff.</p>
          <p className="text-xs text-slate-400">
            If you have only run one version, apply an AST patch in Fix My Agent (Stage 7) or train an adapter (Stage 8) to create v1.1.
          </p>
        </div>
      )}
    </div>
  );
};
