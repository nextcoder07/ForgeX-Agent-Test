import React from 'react';
import type { RegressionComparison } from '../api/client';
import { GitCompare, ArrowUp, ArrowDown, CheckCircle2, AlertTriangle, Minus } from 'lucide-react';

interface RegressionViewProps {
  comparison: RegressionComparison;
}

const DeltaChip: React.FC<{ value: number; label: string }> = ({ value, label }) => {
  const isPositive = value > 0;
  const isNeutral = value === 0;
  return (
    <div className={`p-3 rounded-xl border space-y-1 ${
      isNeutral
        ? 'bg-slate-900 border-slate-700'
        : isPositive
        ? 'bg-emerald-950/40 border-emerald-500/40'
        : 'bg-rose-950/40 border-rose-500/40'
    }`}>
      <span className="text-[10px] uppercase font-bold text-slate-400">{label}</span>
      <div className="flex items-center space-x-1">
        {isNeutral ? (
          <Minus className="w-4 h-4 text-slate-400" />
        ) : isPositive ? (
          <ArrowUp className="w-4 h-4 text-emerald-400" />
        ) : (
          <ArrowDown className="w-4 h-4 text-rose-400" />
        )}
        <span className={`text-xl font-extrabold font-mono ${
          isNeutral ? 'text-slate-300' : isPositive ? 'text-emerald-300' : 'text-rose-300'
        }`}>
          {isPositive ? '+' : ''}{value.toFixed(1)}
        </span>
      </div>
    </div>
  );
};

export const RegressionView: React.FC<RegressionViewProps> = ({ comparison }) => {
  return (
    <div className="p-6 rounded-2xl glass-panel border border-indigo-500/30 bg-slate-950/90 shadow-2xl space-y-6">
      <div>
        <div className="flex items-center space-x-2">
          <GitCompare className="w-5 h-5 text-indigo-400" />
          <h3 className="text-base font-bold text-slate-100">Version Regression Comparison</h3>
        </div>
        <p className="text-xs text-slate-400 mt-0.5">
          <span className="font-mono text-slate-300">{comparison.from_version}</span>
          {' → '}
          <span className="font-mono text-slate-300">{comparison.to_version}</span>
        </p>
      </div>

      {/* Verdict Banner */}
      <div className={`p-4 rounded-xl border text-sm font-bold flex items-center space-x-3 ${
        comparison.summary_verdict.includes('IMPROVEMENT') || comparison.summary_verdict.includes('PASS')
          ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
          : comparison.summary_verdict.includes('REGRESSION') || comparison.summary_verdict.includes('FAIL')
          ? 'bg-rose-950/40 border-rose-500/40 text-rose-300'
          : 'bg-slate-900 border-slate-700 text-slate-300'
      }`}>
        <span>{comparison.summary_verdict}</span>
      </div>

      {/* Delta Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <DeltaChip value={comparison.safety_delta} label="Safety Delta" />
        <DeltaChip value={comparison.capability_delta} label="Capability Delta" />
        <DeltaChip value={comparison.composite_delta} label="Composite Score Delta" />
      </div>

      {/* Resolved vs New Regressions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/30 space-y-2">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <h4 className="text-xs font-bold text-emerald-300">
              Resolved Failures ({comparison.resolved_failures.length})
            </h4>
          </div>
          {comparison.resolved_failures.length === 0 ? (
            <p className="text-xs text-slate-400 italic">None resolved in this version.</p>
          ) : (
            <ul className="space-y-1">
              {comparison.resolved_failures.map((f, i) => (
                <li key={i} className="text-xs text-emerald-200 flex items-start space-x-2">
                  <span className="text-emerald-400 mt-0.5">✓</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 space-y-2">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            <h4 className="text-xs font-bold text-rose-300">
              New Regressions ({comparison.new_regressions.length})
            </h4>
          </div>
          {comparison.new_regressions.length === 0 ? (
            <p className="text-xs text-slate-400 italic">No new regressions introduced.</p>
          ) : (
            <ul className="space-y-1">
              {comparison.new_regressions.map((r, i) => (
                <li key={i} className="text-xs text-rose-200 flex items-start space-x-2">
                  <span className="text-rose-400 mt-0.5">✗</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
