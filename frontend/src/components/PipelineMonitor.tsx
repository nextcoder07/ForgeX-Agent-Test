import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchPipelineRun } from '../api/client';
import type { PipelineRun, PipelineStage } from '../api/client';
import { Radio, CheckCircle2, Clock, Cpu, Sparkles, RefreshCw, ChevronRight, Activity, Terminal } from 'lucide-react';

interface PipelineMonitorProps {
  runId?: string;
  onRefresh?: () => void;
}

export const PipelineMonitor: React.FC<PipelineMonitorProps> = ({ runId = 'default' }) => {
  const navigate = useNavigate();
  const [pipeline, setPipeline] = useState<PipelineRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedStage, setSelectedStage] = useState<PipelineStage | null>(null);

  const loadPipeline = async () => {
    setLoading(true);
    try {
      const data = await fetchPipelineRun(runId);
      setPipeline(data);
      if (data.stages.length > 0 && !selectedStage) {
        setSelectedStage(data.stages[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPipeline();
    const interval = window.setInterval(loadPipeline, 2000);
    return () => window.clearInterval(interval);
  }, [runId]);

  if (!pipeline) {
    return (
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 text-center space-y-2">
        <RefreshCw className="w-5 h-5 text-cyan-400 animate-spin mx-auto" />
        <p className="text-xs text-slate-400">Loading pipeline telemetry...</p>
      </div>
    );
  }

  const completedCount = pipeline.stages.filter(s => s.status === 'completed').length;
  const overallPct = Math.round((completedCount / pipeline.stages.length) * 100);

  return (
    <div className="space-y-4">
      {/* Overview Banner */}
      <div className="p-5 rounded-2xl glass-panel border border-cyan-500/30 bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950/40 shadow-xl flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-cyan-500/20 border border-cyan-500/40 text-cyan-300">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold text-slate-100">Live Pipeline Execution Telemetry</h3>
              <span className="px-2 py-0.5 text-[9px] font-mono uppercase rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                {pipeline.status.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Observability into every stage: Intake → AST Scan → Spec → Strategy → Generation → Critic → Sandbox → Evaluation.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="text-right">
            <span className="text-[10px] text-slate-400 uppercase font-mono block">Overall Progress</span>
            <span className="text-base font-extrabold text-cyan-300 font-mono">{overallPct}% ({completedCount}/{pipeline.stages.length})</span>
          </div>
          <button
            onClick={loadPipeline}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 transition"
            title="Refresh telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Stage Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Stage List */}
        <div className="lg:col-span-2 space-y-2">
          {pipeline.stages.map((stage, idx) => {
            const isSelected = selectedStage?.id === stage.id;
            const isDone = stage.status === 'completed';
            const isRunning = stage.status === 'running';

            return (
              <div
                key={stage.id}
                onClick={() => setSelectedStage(stage)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${
                  isSelected
                    ? 'bg-slate-900 border-cyan-500/60 shadow-lg shadow-cyan-500/10'
                    : 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <span className="w-5 h-5 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center text-[10px] font-mono text-slate-400">
                    {idx + 1}
                  </span>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-slate-200">{stage.display_title}</span>
                      <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded uppercase ${
                        isDone ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/30' :
                        isRunning ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/30 animate-pulse' :
                        'bg-slate-800 text-slate-400'
                      }`}>
                        {stage.status}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono">Stage: {stage.stage_name}</span>
                  </div>
                </div>

                <div className="flex items-center space-x-3 text-right font-mono text-xs">
                  {isDone && (
                    <span className="text-slate-400 text-[11px] flex items-center space-x-1">
                      <Clock className="w-3 h-3 text-slate-500" />
                      <span>{stage.duration_ms.toFixed(1)}ms</span>
                    </span>
                  )}
                  <ChevronRight className={`w-4 h-4 transition-transform ${isSelected ? 'text-cyan-400 translate-x-0.5' : 'text-slate-600'}`} />
                </div>
              </div>
            );
          })}
        </div>

        {/* Stage Telemetry Inspector */}
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/90 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <span className="text-xs font-bold text-slate-300 flex items-center space-x-1.5">
              <Terminal className="w-4 h-4 text-cyan-400" />
              <span>Stage Telemetry Details</span>
            </span>
            {selectedStage && (
              <span className="px-2 py-0.5 text-[9px] font-mono rounded bg-slate-900 text-slate-400 border border-slate-700">
                {selectedStage.stage_name}
              </span>
            )}
          </div>

          {selectedStage ? (
            <div className="space-y-3 text-xs font-mono">
              <div className="space-y-1">
                <span className="text-[10px] uppercase text-slate-500">Stage Title</span>
                <p className="text-slate-200 font-sans font-bold">{selectedStage.display_title}</p>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1">
                <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
                  <span className="text-[9px] text-slate-500 uppercase block">Duration</span>
                  <span className="text-cyan-300 font-bold">{selectedStage.duration_ms.toFixed(1)} ms</span>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
                  <span className="text-[9px] text-slate-500 uppercase block">AI Model</span>
                  <span className="text-indigo-300 font-bold">{selectedStage.model}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
                  <span className="text-[9px] text-slate-500 uppercase block">Input Tokens</span>
                  <span className="text-slate-300 font-bold">{selectedStage.input_tokens}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
                  <span className="text-[9px] text-slate-500 uppercase block">Output Tokens</span>
                  <span className="text-emerald-300 font-bold">{selectedStage.output_tokens}</span>
                </div>
              </div>

              {Object.keys(selectedStage.details).length > 0 && (
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase text-slate-500 block mb-1">Stage Metadata & State</span>
                  <pre className="text-[10px] text-cyan-200 overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(selectedStage.details, null, 2)}
                  </pre>
                </div>
              )}

              <div className="flex flex-wrap gap-2 pt-1">
                {selectedStage.details.execution_job_id && (
                  <button
                    onClick={() => navigate(`/executions?agentId=${pipeline.agent_id}`)}
                    className="rounded-lg border border-emerald-500/40 bg-emerald-950/50 px-2.5 py-1.5 text-[10px] font-bold text-emerald-300"
                  >
                    Open Sandbox Traces
                  </button>
                )}
                {selectedStage.details.evaluation_job_id && (
                  <button
                    onClick={() => navigate(`/evaluations/${selectedStage.details.evaluation_job_id}`)}
                    className="rounded-lg border border-indigo-500/40 bg-indigo-950/50 px-2.5 py-1.5 text-[10px] font-bold text-indigo-300"
                  >
                    Open Evaluation Scorecard
                  </button>
                )}
                {selectedStage.details.repair_session_id && (
                  <button
                    onClick={() => navigate(`/fix-agent?agentId=${pipeline.agent_id}`)}
                    className="rounded-lg border border-rose-500/40 bg-rose-950/50 px-2.5 py-1.5 text-[10px] font-bold text-rose-300"
                  >
                    Open Fix My Agent
                  </button>
                )}
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic text-center py-8">Select a stage on the left to inspect its real telemetry.</p>
          )}
        </div>
      </div>
    </div>
  );
};
