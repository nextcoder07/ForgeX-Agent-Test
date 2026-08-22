import React from 'react';
import type { StrategyPlan } from '../api/client';
import { Layers, ShieldAlert, Sparkles, CheckCircle2, Target } from 'lucide-react';

interface ScenarioStrategyViewProps {
  strategy: StrategyPlan;
  onGenerateClick?: () => void;
  isGenerating?: boolean;
}

const CATEGORY_COLORS: Record<string, { badge: string; border: string }> = {
  normal: { badge: 'bg-emerald-950 text-emerald-300 border-emerald-500/30', border: 'border-emerald-500/20' },
  edge: { badge: 'bg-blue-950 text-blue-300 border-blue-500/30', border: 'border-blue-500/20' },
  recovery: { badge: 'bg-indigo-950 text-indigo-300 border-indigo-500/30', border: 'border-indigo-500/20' },
  adversarial: { badge: 'bg-amber-950 text-amber-300 border-amber-500/30', border: 'border-amber-500/20' },
  safety: { badge: 'bg-rose-950 text-rose-300 border-rose-500/30', border: 'border-rose-500/20' },
  security: { badge: 'bg-purple-950 text-purple-300 border-purple-500/30', border: 'border-purple-500/20' },
  stress: { badge: 'bg-cyan-950 text-cyan-300 border-cyan-500/30', border: 'border-cyan-500/20' },
  chaos: { badge: 'bg-pink-950 text-pink-300 border-pink-500/30', border: 'border-pink-500/20' },
};

export const ScenarioStrategyView: React.FC<ScenarioStrategyViewProps> = ({
  strategy,
  onGenerateClick,
  isGenerating = false,
}) => {
  return (
    <div className="p-6 rounded-2xl glass-panel border border-indigo-500/30 bg-slate-950/90 shadow-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Target className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-bold text-slate-100">Tailored 8-Category Test Strategy Plan</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">{strategy.summary}</p>
        </div>

        <div className="flex items-center space-x-3">
          <span className="text-xs font-mono font-bold text-cyan-300 bg-cyan-950/50 px-3 py-1.5 rounded-xl border border-cyan-500/30">
            Total Scenarios: {strategy.total_target}
          </span>
          {onGenerateClick && (
            <button
              onClick={onGenerateClick}
              disabled={isGenerating}
              className="px-4 py-1.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-600 hover:to-indigo-700 text-slate-100 font-bold text-xs shadow-lg shadow-cyan-500/20 transition disabled:opacity-50"
            >
              {isGenerating ? 'Generating & Critiquing...' : 'Generate Scenarios Now'}
            </button>
          )}
        </div>
      </div>

      {/* 8-Category Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {strategy.category_distribution.map((catTarget) => {
          const catKey = catTarget.category.toLowerCase();
          const colors = CATEGORY_COLORS[catKey] || {
            badge: 'bg-slate-800 text-slate-300 border-slate-700',
            border: 'border-slate-800',
          };

          return (
            <div
              key={catTarget.category}
              className={`p-4 rounded-xl glass-card border ${colors.border} space-y-2 flex flex-col justify-between`}
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span
                    className={`px-2 py-0.5 text-[10px] font-mono uppercase font-bold rounded border ${colors.badge}`}
                  >
                    {catTarget.category}
                  </span>
                  <span className="font-mono text-xs font-bold text-slate-200">
                    {catTarget.target_count} tests
                  </span>
                </div>
                <p className="text-xs font-bold text-slate-100">{catTarget.focus_risk}</p>
              </div>
              <p className="text-[11px] text-slate-400 font-sans leading-relaxed pt-1 border-t border-slate-800/80">
                {catTarget.rationale}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
