import React from 'react';
import type { ReliabilityScorecard } from '../api/client';
import { ShieldCheck, Zap, CheckCircle2, Target, Activity, BarChart3, Cpu } from 'lucide-react';

interface TwoAxisQuadrantProps {
  scorecard: ReliabilityScorecard;
}

export const TwoAxisQuadrant: React.FC<TwoAxisQuadrantProps> = ({ scorecard }) => {
  const safetyPct = scorecard.safety_axis;
  const capabilityPct = scorecard.capability_axis;

  // Quadrant classification
  const isHighSafety = safetyPct >= 70;
  const isHighCapability = capabilityPct >= 70;
  const quadrantLabel = isHighSafety && isHighCapability
    ? 'Production Ready'
    : !isHighSafety && isHighCapability
    ? 'Capable but Unsafe'
    : isHighSafety && !isHighCapability
    ? 'Safe but Limited'
    : 'Needs Fundamental Work';

  const quadrantColor = isHighSafety && isHighCapability
    ? 'text-emerald-400 bg-emerald-950/30 border-emerald-500/40'
    : !isHighSafety && isHighCapability
    ? 'text-amber-400 bg-amber-950/30 border-amber-500/40'
    : isHighSafety && !isHighCapability
    ? 'text-cyan-400 bg-cyan-950/30 border-cyan-500/40'
    : 'text-rose-400 bg-rose-950/30 border-rose-500/40';

  const metrics = [
    { label: 'Correctness', value: scorecard.correctness, icon: CheckCircle2, color: 'from-cyan-500 to-cyan-700' },
    { label: 'Safety', value: scorecard.safety, icon: ShieldCheck, color: 'from-emerald-500 to-emerald-700' },
    { label: 'Robustness', value: scorecard.robustness, icon: Activity, color: 'from-indigo-500 to-indigo-700' },
    { label: 'Tool Discipline', value: scorecard.tool_discipline, icon: Cpu, color: 'from-violet-500 to-violet-700' },
    { label: 'Goal Adherence', value: scorecard.goal_adherence, icon: Target, color: 'from-amber-500 to-amber-700' },
  ];

  return (
    <div className="p-6 rounded-2xl glass-panel border border-indigo-500/30 bg-slate-950/90 shadow-2xl space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-bold text-slate-100">2D Reliability Scorecard: Safety × Capability</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {scorecard.agent_name} ({scorecard.agent_version}) · {scorecard.total_scenarios} scenarios evaluated
          </p>
        </div>
        <div className={`px-4 py-2 rounded-xl border text-sm font-extrabold ${quadrantColor}`}>
          {quadrantLabel}
        </div>
      </div>

      {/* 2D Scatter Quadrant */}
      <div className="relative w-full h-64 bg-slate-900/90 rounded-xl border border-slate-800 p-4">
        {/* Inner Grid Container */}
        <div className="relative w-full h-full border border-slate-700/60 rounded-lg overflow-hidden">
          {/* Quadrant Lines */}
          <div className="absolute inset-0 flex flex-col pointer-events-none">
            <div className="h-1/2 border-b border-slate-700/60 flex">
              <div className="w-1/2 border-r border-slate-700/60 flex items-center justify-center">
                <span className="text-[10px] font-mono text-slate-500 text-center px-2">Safe but<br/>Limited</span>
              </div>
              <div className="w-1/2 flex items-center justify-center">
                <span className="text-[10px] font-mono text-emerald-400/80 font-bold text-center px-2">⭐ Production<br/>Ready</span>
              </div>
            </div>
            <div className="h-1/2 flex">
              <div className="w-1/2 border-r border-slate-700/60 flex items-center justify-center">
                <span className="text-[10px] font-mono text-rose-400/80 text-center px-2">Needs<br/>Work</span>
              </div>
              <div className="w-1/2 flex items-center justify-center">
                <span className="text-[10px] font-mono text-amber-400/80 text-center px-2">Capable but<br/>Unsafe</span>
              </div>
            </div>
          </div>

          {/* Axis Labels */}
          <div className="absolute bottom-1 left-1/2 -translate-x-1/2 text-[9px] font-mono text-slate-400 font-bold">
            ← Safety Axis (0 to 100%) →
          </div>
          <div className="absolute left-1 top-1/2 -translate-y-1/2 text-[9px] font-mono text-slate-400 font-bold rotate-[-90deg]">
            ← Capability (0 to 100%) →
          </div>

          {/* Inset Position Calculation (6% to 94% mapping so dot sits inside grid cleanly) */}
          {(() => {
            const clampLeft = 6 + (Math.max(0, Math.min(100, safetyPct)) / 100) * 88;
            const clampTop = 6 + ((100 - Math.max(0, Math.min(100, capabilityPct))) / 100) * 88;
            return (
              <div
                className="absolute flex items-center gap-2 -translate-x-1/2 -translate-y-1/2 z-20"
                style={{
                  left: `${clampLeft}%`,
                  top: `${clampTop}%`,
                }}
              >
                {/* Glowing Agent Position Marker */}
                <div className="relative flex items-center justify-center">
                  <span className="absolute w-6 h-6 rounded-full bg-cyan-400/30 animate-ping" />
                  <div className="w-5 h-5 rounded-full border-2 border-white bg-cyan-500 shadow-lg shadow-cyan-500/50 flex items-center justify-center z-10">
                    <span className="w-2 h-2 rounded-full bg-white" />
                  </div>
                </div>

                {/* Score Position Tooltip Badge */}
                <div className="px-2 py-1 rounded bg-slate-950/95 border border-cyan-500/40 text-[10px] font-mono text-cyan-300 shadow-xl whitespace-nowrap hidden sm:block">
                  <strong>Safety:</strong> {safetyPct}% · <strong>Capability:</strong> {capabilityPct}%
                </div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* Axis Scores */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <span className="text-[10px] uppercase font-bold text-emerald-400 block mb-1">X-Axis: Safety</span>
          <div className="flex items-end space-x-2">
            <span className="text-2xl font-extrabold text-emerald-300 font-mono">{safetyPct}</span>
            <span className="text-sm text-slate-400 mb-0.5">/ 100</span>
          </div>
          <div className="mt-2 w-full h-1.5 bg-slate-800 rounded-full">
            <div className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full" style={{ width: `${safetyPct}%` }} />
          </div>
        </div>
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <span className="text-[10px] uppercase font-bold text-cyan-400 block mb-1">Y-Axis: Capability</span>
          <div className="flex items-end space-x-2">
            <span className="text-2xl font-extrabold text-cyan-300 font-mono">{capabilityPct}</span>
            <span className="text-sm text-slate-400 mb-0.5">/ 100</span>
          </div>
          <div className="mt-2 w-full h-1.5 bg-slate-800 rounded-full">
            <div className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 rounded-full" style={{ width: `${capabilityPct}%` }} />
          </div>
        </div>
      </div>

      {/* 5-Dimension Breakdown */}
      <div className="space-y-2">
        <span className="text-[10px] uppercase font-bold text-slate-400">Five Dimension Breakdown:</span>
        {metrics.map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="flex items-center space-x-3 text-xs">
              <Icon className="w-4 h-4 text-slate-400 shrink-0" />
              <span className="w-28 text-slate-300">{m.label}</span>
              <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full bg-gradient-to-r ${m.color} rounded-full transition-all duration-500`}
                  style={{ width: `${m.value}%` }}
                />
              </div>
              <span className="w-8 text-right font-mono font-bold text-slate-200">{m.value}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
