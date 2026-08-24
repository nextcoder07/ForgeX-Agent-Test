import React from 'react';
import { useNavigate, useParams } from "react-router-dom";
import { PipelineMonitor } from '../components/PipelineMonitor';
import { Radio, Activity, Boxes, Play, ShieldCheck } from 'lucide-react';

export const PipelineObservabilityPage: React.FC = () => {
  const activeRunId = localStorage.getItem('lastPipelineRunId');

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center space-x-2.5">
          <Radio className="w-5 h-5 sm:w-6 sm:h-6 text-cyan-400" />
          <span>Project Evaluation Pipeline</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-300 mt-1">
          Follow the active agent from scenario generation through sandbox execution to evidence-backed evaluation.
        </p>
      </div>

      {activeRunId ? (
        <PipelineMonitor runId={activeRunId} />
      ) : (
        <div className="p-5 sm:p-6 rounded-2xl glass-panel border border-slate-700 text-center space-y-2">
          <Play className="w-5 h-5 text-cyan-400 mx-auto" />
          <h2 className="text-xs sm:text-sm font-bold text-slate-100">No project pipeline run selected</h2>
          <p className="text-xs text-slate-300">Start an intake or full evaluation run to see its live stages here.</p>
        </div>
      )}

      {/* Actual project workflow */}
      <div className="p-3.5 sm:p-5 rounded-2xl glass-panel border border-slate-700/80 space-y-3">
        <h2 className="text-xs sm:text-sm font-bold text-slate-100 flex items-center space-x-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span>Project Workflow</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { label: '1. Scenario Generation', desc: 'Build or select scenarios for the chosen agent, covering normal, edge, safety, security, and stress behavior.', icon: Boxes, color: 'border-cyan-500/40 text-cyan-300' },
            { label: '2. Sandbox Execution', desc: 'Run the selected agent in an isolated environment and capture tool calls, outputs, state changes, and security events.', icon: Activity, color: 'border-emerald-500/40 text-emerald-300' },
            { label: '3. Evidence Evaluation', desc: 'Evaluate immutable traces with deterministic assertions and semantic review, then produce verdicts, scorecards, and fixes.', icon: ShieldCheck, color: 'border-indigo-500/40 text-indigo-300' },
          ].map((stage) => (
            <div key={stage.label} className={`p-3 rounded-xl glass-card border ${stage.color.split(' ')[0]} space-y-1`}>
              <div className="flex items-center gap-2"><stage.icon className={`w-3.5 h-3.5 ${stage.color.split(' ')[1]}`} /><span className={`text-[10px] font-bold font-mono uppercase ${stage.color.split(' ')[1]}`}>{stage.label}</span></div>
              <p className="text-[11px] text-slate-300 leading-relaxed">{stage.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
