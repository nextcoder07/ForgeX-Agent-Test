import React, { useState, useEffect } from 'react';
import { fetchAgents, runEvaluationJob, fetchScorecard, fetchFailureClusters } from '../api/client';
import type { AgentRecord, ReliabilityScorecard, FailureCluster } from '../api/client';
import { TwoAxisQuadrant } from '../components/TwoAxisQuadrant';
import { FailureClustersView } from '../components/FailureClustersView';
import { RefreshCw, Zap, CheckCircle2, ShieldCheck, BarChart3, AlertTriangle, Clock, Cpu } from 'lucide-react';
import type { PageId } from '../components/Navbar';

interface EvaluationRunPageProps {
  onNavigate: (page: PageId) => void;
}

export const EvaluationRunPage: React.FC<EvaluationRunPageProps> = ({ onNavigate }) => {
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [batchSize, setBatchSize] = useState(25);
  const [running, setRunning] = useState(false);
  const [jobResult, setJobResult] = useState<any | null>(null);
  const [scorecard, setScorecard] = useState<ReliabilityScorecard | null>(null);
  const [clusters, setClusters] = useState<FailureCluster[]>([]);

  useEffect(() => {
    fetchAgents().then((list) => {
      setAgents(list);
      if (list.length > 0) setSelectedAgentId(list[0].id);
    });
  }, []);

  const handleRunEvaluation = async () => {
    if (!selectedAgentId) return;
    setRunning(true);
    setJobResult(null);
    setScorecard(null);
    setClusters([]);

    try {
      const result = await runEvaluationJob(selectedAgentId, batchSize);
      setJobResult(result);

      if (result.job_id || result.id) {
        const evalId = result.job_id || result.id;
        const [sc, clust] = await Promise.all([
          fetchScorecard(evalId),
          fetchFailureClusters(evalId),
        ]);
        setScorecard(sc);
        setClusters(clust);
      }
    } catch (e: any) {
      console.error(e);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">Evaluation & Reliability Engine</h1>
        <p className="text-sm text-slate-400 mt-1">
          Run a full sandboxed evaluation batch. The engine executes scenarios with fault injection, scores every run with a hybrid rule + LLM judge, proves failure causation via counterfactual replay, and produces a 2D reliability scorecard.
        </p>
      </div>

      {/* Launch Controls */}
      <div className="p-5 rounded-2xl glass-panel border border-indigo-500/30 bg-gradient-to-r from-slate-950 via-indigo-950/20 to-slate-950 space-y-4">
        <h2 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
          <Zap className="w-4 h-4 text-indigo-400" />
          <span>Launch Evaluation Job</span>
        </h2>

        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-48">
            <label className="text-xs font-semibold text-slate-400 block mb-1">Target Agent:</label>
            <select
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              className="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-cyan-300 font-mono text-xs focus:outline-none focus:border-indigo-500 transition"
            >
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name || a.name} · registered: {a.name} · {a.version_label}
                </option>
              ))}
              {agents.length === 0 && <option>No agents — use Intake page first</option>}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-1">Scenario Batch Size:</label>
            <input
              type="number"
              min={5}
              max={100}
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
              className="w-24 p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 font-mono text-xs focus:outline-none focus:border-indigo-500 transition text-center"
            />
          </div>

          <button
            onClick={handleRunEvaluation}
            disabled={running || !selectedAgentId}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 via-violet-600 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-slate-100 font-bold text-sm shadow-lg shadow-indigo-500/20 flex items-center space-x-2 transition disabled:opacity-50"
          >
            {running ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Running Evaluation... (includes counterfactuals)</span>
              </>
            ) : (
              <>
                <Zap className="w-4 h-4" />
                <span>Launch Full Evaluation</span>
              </>
            )}
          </button>
        </div>

        {running && (
          <div className="p-3 rounded-xl bg-indigo-950/40 border border-indigo-500/30 text-xs text-indigo-300 space-y-1">
            <p className="font-bold flex items-center space-x-2">
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>Evaluation Pipeline Running...</span>
            </p>
            <p className="text-slate-400">
              Executing {batchSize} scenarios → Applying fault injections → Scoring with hybrid evaluator → Running counterfactual replays → Clustering failures...
            </p>
          </div>
        )}
      </div>

      {/* Job Summary */}
      {jobResult && (
        <div className="p-5 rounded-2xl glass-panel border border-slate-700 space-y-4">
          <h2 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
            <BarChart3 className="w-4 h-4 text-emerald-400" />
            <span>Evaluation Job Complete</span>
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase block">Job ID</span>
              <span className="text-cyan-300 font-bold">{jobResult.job_id || jobResult.id}</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase block">Status</span>
              <span className="text-emerald-300 font-bold uppercase">{jobResult.status}</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase block">Verdicts</span>
              <span className="text-slate-200 font-bold">{jobResult.total_verdicts ?? batchSize}</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase block">Agent</span>
              <span className="text-slate-200 font-bold">{jobResult.agent_id || selectedAgentId}</span>
            </div>
          </div>
        </div>
      )}

      {/* Scorecard */}
      {scorecard && (
        <div>
          <TwoAxisQuadrant scorecard={scorecard} />
        </div>
      )}

      {/* Failure Clusters */}
      {clusters.length > 0 && (
        <div>
          <h2 className="text-base font-bold text-slate-100 mb-4">
            Failure Clusters ({clusters.length} identified)
          </h2>
          <FailureClustersView clusters={clusters} />
        </div>
      )}

      {!jobResult && !running && (
        <div className="py-16 text-center space-y-3">
          <Zap className="w-12 h-12 mx-auto text-slate-700" />
          <p className="text-sm text-slate-400">Select an agent and click Launch Full Evaluation to begin.</p>
          <p className="text-[11px] text-slate-500">Results include scorecard, failure clusters, and counterfactual causation proof.</p>
        </div>
      )}
    </div>
  );
};
