import React from 'react';
import type { SpecConflict } from '../api/client';
import { AlertTriangle, ShieldAlert, ArrowRight, CheckCircle2, FileText, Code } from 'lucide-react';

interface SpecConflictCardProps {
  conflicts: SpecConflict[];
}

export const SpecConflictCard: React.FC<SpecConflictCardProps> = ({ conflicts }) => {
  if (!conflicts || conflicts.length === 0) {
    return (
      <div className="p-4 rounded-xl glass-panel border border-emerald-500/30 bg-emerald-950/10 text-emerald-300 text-xs flex items-center space-x-2">
        <CheckCircle2 className="w-4 h-4 shrink-0" />
        <span>No specification conflicts detected. Code implementation strictly matches documented safety policies.</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center space-x-2">
        <AlertTriangle className="w-4 h-4 text-amber-400" />
        <h4 className="text-sm font-bold text-slate-100">
          Specification Conflicts Detected ({conflicts.length})
        </h4>
        <span className="px-2 py-0.5 text-[9px] font-mono rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
          Doc Claim vs Code Reality
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3">
        {conflicts.map((conflict) => {
          const isCritical = conflict.risk_level === 'critical';
          const isHigh = conflict.risk_level === 'high';

          return (
            <div
              key={conflict.id}
              className={`p-4 rounded-xl glass-panel border space-y-3 ${
                isCritical
                  ? 'border-rose-500/40 bg-rose-950/20'
                  : isHigh
                  ? 'border-amber-500/40 bg-amber-950/20'
                  : 'border-indigo-500/40 bg-indigo-950/20'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-xs text-slate-100">{conflict.title}</span>
                <span
                  className={`px-2 py-0.5 text-[9px] uppercase font-bold rounded ${
                    isCritical
                      ? 'bg-rose-900/60 text-rose-300 border border-rose-500/40'
                      : isHigh
                      ? 'bg-amber-900/60 text-amber-300 border border-amber-500/40'
                      : 'bg-indigo-900/60 text-indigo-300 border border-indigo-500/40'
                  }`}
                >
                  {conflict.risk_level} Discrepancy
                </span>
              </div>

              {/* Side by side comparison */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                {/* Doc claim */}
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-mono uppercase text-slate-400 font-bold flex items-center space-x-1">
                    <FileText className="w-3 h-3 text-cyan-400" />
                    <span>Documentation / Policy Claim</span>
                  </span>
                  <p className="text-slate-200 text-xs italic font-serif leading-relaxed">
                    "{conflict.doc_claim}"
                  </p>
                </div>

                {/* Code reality */}
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-mono uppercase text-slate-400 font-bold flex items-center space-x-1">
                    <Code className="w-3 h-3 text-rose-400" />
                    <span>AST Code Implementation Reality</span>
                  </span>
                  <p className="text-rose-200 text-xs font-mono leading-relaxed">
                    {conflict.code_reality}
                  </p>
                </div>
              </div>

              <p className="text-slate-400 text-xs leading-relaxed">{conflict.explanation}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
