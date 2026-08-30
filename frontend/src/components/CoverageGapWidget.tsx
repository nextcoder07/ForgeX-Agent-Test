import React from 'react';
import type { CoverageGapReport } from '../api/client';
import { AlertCircle, CheckCircle2, Wrench, ShieldAlert, Sparkles } from 'lucide-react';

interface CoverageGapWidgetProps {
  report: CoverageGapReport;
  onGenerateTargeted?: () => void;
}

export const CoverageGapWidget: React.FC<CoverageGapWidgetProps> = ({ report, onGenerateTargeted }) => {
  return (
    <div className="p-5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/90 shadow-xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
            Test Coverage Gap Engine
          </h3>
        </div>
        <span className="text-xs font-mono font-bold text-cyan-300">
          Overall Coverage: {report.overall_coverage_pct}%
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        {/* Tool Coverage */}
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
          <span className="text-[10px] uppercase font-bold text-slate-500 flex items-center space-x-1">
            <Wrench className="w-3 h-3 text-slate-400" />
            <span>Tools Exercised</span>
          </span>
          <p className="text-base font-extrabold text-slate-100 font-mono">
            {report.exercised_tools} / {report.total_tools} Tools
          </p>
          {report.total_tools === 0 ? (
            <p className="text-[10px] text-slate-500 font-mono">
              No agent tools detected.
            </p>
          ) : (
            report.unexercised_tools.length > 0 && (
              <p className="text-[10px] text-amber-300/80 font-mono truncate">
                Unexercised: {report.unexercised_tools.join(', ')}
              </p>
            )
          )}
        </div>

        {/* Category Coverage Progress */}
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 col-span-2 space-y-2">
          <span className="text-[10px] uppercase font-bold text-slate-500 block">
            Category Depth Breakdown
          </span>
          <div className="grid grid-cols-4 gap-2">
            {Object.entries(report.category_coverage).map(([cat, score]) => (
              <div key={cat} className="space-y-0.5">
                <div className="flex justify-between text-[9px] font-mono text-slate-400">
                  <span className="uppercase">{cat}</span>
                  <span className="text-cyan-300">{score}%</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      score >= 80 ? 'bg-emerald-500' : score >= 50 ? 'bg-cyan-500' : 'bg-amber-500'
                    }`}
                    style={{ width: `${score}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Coverage Gaps Detected Alerts */}
      {report.gaps_detected.length > 0 && (
        <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-500/30 flex items-center justify-between">
          <div className="space-y-0.5">
            <span className="text-xs font-bold text-amber-300 flex items-center space-x-1.5">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>Coverage Gaps Detected ({report.gaps_detected.length})</span>
            </span>
            <p className="text-[11px] text-slate-400">{report.gaps_detected[0]}</p>
          </div>

          {onGenerateTargeted && (
            <button
              onClick={onGenerateTargeted}
              className="px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 text-xs font-bold transition flex items-center space-x-1 shrink-0"
            >
              <Sparkles className="w-3 h-3" />
              <span>Generate Targeted Tests</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
};
