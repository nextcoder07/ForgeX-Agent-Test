import React from 'react';
import { PipelineMonitor } from '../components/PipelineMonitor';
import { Radio, Activity } from 'lucide-react';

export const PipelineObservabilityPage: React.FC = () => {
  const activeRunId = localStorage.getItem('lastPipelineRunId') || 'default';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
          <Radio className="w-6 h-6 text-cyan-400" />
          <span>Pipeline Execution Telemetry Monitor</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Real-time observability into every stage of the evaluation pipeline. Shows actual duration in milliseconds, token counts per AI call, retry counts, and stage status — not animated fake percentages.
        </p>
      </div>

      <PipelineMonitor runId={activeRunId} />

      {/* Stage Guide */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <h2 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span>Pipeline Stage Guide</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: '1. Agent Intake', desc: 'Upload normalization: files are hashed, stored, and indexed. AST parser extracts tool signatures from Python/TS source.', color: 'border-cyan-500/30 text-cyan-300' },
            { label: '2. Spec Reconstruction', desc: 'Gemini 2.5 Flash reads the AST output and your system prompt to reconstruct a complete normalized spec with goals, risks, and tool inventory.', color: 'border-indigo-500/30 text-indigo-300' },
            { label: '3. Conflict Detection', desc: 'Cross-references documented safety claims with actual code implementation to surface discrepancies.', color: 'border-amber-500/30 text-amber-300' },
            { label: '4. Strategy Planning', desc: 'Plans 8-category scenario distribution based on agent risk surface and domain.', color: 'border-violet-500/30 text-violet-300' },
            { label: '5. Scenario Generation', desc: 'Generates adversarial and normal test cases using the strategy plan. Each scenario targets a specific risk.', color: 'border-blue-500/30 text-blue-300' },
            { label: '6. Critic Review', desc: 'Each generated scenario passes through a critic that filters low-quality or invalid scenarios before library entry.', color: 'border-rose-500/30 text-rose-300' },
            { label: '7. Sandbox Execution', desc: 'Runs scenarios in ephemeral sandboxes. Tool calls are intercepted, faults are injected, state changes are recorded.', color: 'border-emerald-500/30 text-emerald-300' },
            { label: '8. Hybrid Evaluation', desc: 'Deterministic rules + LLM judge score each execution trace. Counterfactual replays prove causation.', color: 'border-pink-500/30 text-pink-300' },
          ].map((stage) => (
            <div key={stage.label} className={`p-3 rounded-xl glass-card border ${stage.color.split(' ')[0]} space-y-1`}>
              <span className={`text-[10px] font-bold font-mono uppercase ${stage.color.split(' ')[1]}`}>{stage.label}</span>
              <p className="text-[11px] text-slate-400 leading-relaxed">{stage.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
