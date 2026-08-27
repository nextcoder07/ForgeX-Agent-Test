import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  Lock,
  ArrowRight,
  Sparkles,
  AlertTriangle,
  PlayCircle,
  Cpu,
  Layers,
  ShieldCheck,
  Search,
  Wrench,
  BarChart3
} from 'lucide-react';
import { AgentPipelineStageStatus, fetchAgentPipelineStageStatus } from '../api/client';

interface PipelineSequenceTrackerProps {
  agentId: string;
  currentStageId?: string;
  onRefresh?: () => void;
}

export const PipelineSequenceTracker: React.FC<PipelineSequenceTrackerProps> = ({
  agentId,
  currentStageId,
  onRefresh
}) => {
  const navigate = useNavigate();
  const [pipelineStatus, setPipelineStatus] = useState<AgentPipelineStageStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!agentId) return;
    let isMounted = true;
    fetchAgentPipelineStageStatus(agentId)
      .then((data) => {
        if (isMounted) {
          setPipelineStatus(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch pipeline status:', err);
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [agentId, currentStageId]);

  if (!agentId || !pipelineStatus) return null;

  const getStageIcon = (stageId: string) => {
    switch (stageId) {
      case 'intake': return <Layers className="w-3.5 h-3.5" />;
      case 'scenarios': return <Sparkles className="w-3.5 h-3.5" />;
      case 'dependencies': return <ShieldCheck className="w-3.5 h-3.5" />;
      case 'executions': return <PlayCircle className="w-3.5 h-3.5" />;
      case 'evaluations': return <BarChart3 className="w-3.5 h-3.5" />;
      case 'diagnosis': return <Search className="w-3.5 h-3.5" />;
      case 'fix-agent': return <Wrench className="w-3.5 h-3.5" />;
      case 'training': return <Cpu className="w-3.5 h-3.5" />;
      case 'regression': return <CheckCircle2 className="w-3.5 h-3.5" />;
      default: return <Layers className="w-3.5 h-3.5" />;
    }
  };

  return (
    <div className="mb-6 rounded-2xl border border-slate-800/80 bg-slate-900/90 backdrop-blur-xl p-4 shadow-xl shadow-black/40">
      {/* Top Bar: Progress & Next Step Guidance */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3.5 mb-3.5 border-b border-slate-800/60">
        <div className="flex items-center space-x-3">
          <div className="px-2.5 py-1 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono font-medium">
            Agent: {pipelineStatus.agent_name} ({pipelineStatus.current_version})
          </div>
          <div className="text-xs text-slate-400">
            Pipeline Progress: <span className="font-semibold text-white font-mono">{pipelineStatus.overall_pipeline_progress}%</span>
          </div>
          {pipelineStatus.latest_scorecard_score !== null && pipelineStatus.latest_scorecard_score !== undefined && pipelineStatus.evaluated_verdicts_count > 0 && (
            <div className={`px-2 py-0.5 rounded text-[11px] font-mono ${
              pipelineStatus.latest_scorecard_score >= 80 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' :
              pipelineStatus.latest_scorecard_score >= 50 ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' :
              'bg-rose-500/10 text-rose-400 border border-rose-500/30'
            }`}>
              Reliability Score: {pipelineStatus.latest_scorecard_score.toFixed(1)}/100
            </div>
          )}
        </div>

        {/* Action Button for Next Recommended Stage */}
        <div className="flex items-center space-x-2">
          {pipelineStatus.total_failures_count > 0 && (
            <div className="flex items-center space-x-1 text-xs text-rose-400 bg-rose-950/40 px-2.5 py-1 rounded-lg border border-rose-800/40">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
              <span>{pipelineStatus.total_failures_count} Failures ({pipelineStatus.critical_failures_count} Critical)</span>
            </div>
          )}
          <button
            onClick={() => {
              const targetStage = pipelineStatus.stages.find(s => s.stage_id === pipelineStatus.recommended_next_stage);
              if (targetStage) navigate(targetStage.next_action_route);
            }}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white text-xs font-semibold shadow-md shadow-cyan-500/20 transition-all cursor-pointer"
          >
            <span>Next: {pipelineStatus.stages.find(s => s.stage_id === pipelineStatus.recommended_next_stage)?.next_action_label || 'Proceed'}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Horizontal Stage Stepper */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-9 gap-2">
        {pipelineStatus.stages.map((stage) => {
          const isCurrent = currentStageId === stage.stage_id;
          const isCompleted = stage.is_completed;
          const isBlocked = stage.is_blocked;
          const isOptional = stage.status === 'OPTIONAL_AVAILABLE';

          let cardStyle = 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700';
          if (isCurrent) {
            cardStyle = 'border-cyan-500/80 bg-cyan-950/30 text-cyan-300 shadow-md shadow-cyan-500/10 ring-1 ring-cyan-500/50';
          } else if (isCompleted) {
            cardStyle = 'border-emerald-500/40 bg-emerald-950/20 text-emerald-300 hover:border-emerald-500/60';
          } else if (isBlocked) {
            cardStyle = 'border-slate-800/60 bg-slate-950/20 text-slate-600 opacity-70 cursor-not-allowed';
          } else if (isOptional) {
            cardStyle = 'border-purple-500/30 bg-purple-950/20 text-purple-300 hover:border-purple-500/60';
          }

          return (
            <div
              key={stage.stage_id}
              onClick={() => {
                if (!isBlocked) navigate(stage.next_action_route);
              }}
              title={stage.blocker_reason || stage.metrics_summary || stage.name}
              className={`p-2 rounded-xl border text-left transition-all relative group ${cardStyle} ${!isBlocked ? 'cursor-pointer' : ''}`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center space-x-1.5 text-xs font-mono">
                  {getStageIcon(stage.stage_id)}
                  <span className="font-bold text-[11px]">#{stage.stage_number}</span>
                </div>
                {isCompleted ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : isBlocked ? (
                  <Lock className="w-3 h-3 text-slate-500" />
                ) : isCurrent ? (
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                ) : null}
              </div>

              <div className="text-[11px] font-semibold truncate leading-tight">
                {stage.name.replace(/^\d+\.\s*/, '')}
              </div>

              {stage.metrics_summary && (
                <div className="text-[10px] text-slate-400 truncate mt-0.5">
                  {stage.metrics_summary}
                </div>
              )}

              {/* Blocker Tooltip on Hover */}
              {isBlocked && stage.blocker_reason && (
                <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 p-2 rounded-lg bg-slate-900 border border-amber-500/40 text-amber-300 text-[11px] z-50 shadow-2xl">
                  <div className="flex items-start space-x-1">
                    <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0 mt-0.5" />
                    <span>{stage.blocker_reason}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
