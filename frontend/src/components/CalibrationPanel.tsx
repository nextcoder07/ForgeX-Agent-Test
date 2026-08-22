import React from 'react';
import type { CalibrationReport } from '../api/client';
import { CheckCircle2, XCircle, AlertTriangle, Activity, BarChart3 } from 'lucide-react';

interface CalibrationPanelProps {
  report: CalibrationReport;
}

export const CalibrationPanel: React.FC<CalibrationPanelProps> = ({ report }) => {
  const agreementPct = (report.agreement_rate * 100).toFixed(1);
  const fpPct = report.total_samples > 0 ? ((report.false_positives / report.total_samples) * 100).toFixed(1) : '0';
  const fnPct = report.total_samples > 0 ? ((report.false_negatives / report.total_samples) * 100).toFixed(1) : '0';

  return (
    <div className="space-y-6">
      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl bg-gradient-to-b from-emerald-950/40 to-slate-950 border border-emerald-500/30 space-y-1">
          <span className="text-[10px] font-mono uppercase text-emerald-400 font-bold block">Judge Agreement</span>
          <p className="text-2xl font-extrabold text-emerald-300 font-mono">{agreementPct}%</p>
          <p className="text-[10px] text-slate-400">{report.agreed_samples}/{report.total_samples} samples</p>
        </div>
        <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
          <span className="text-[10px] font-mono uppercase text-slate-400 font-bold block">Total Samples</span>
          <p className="text-2xl font-extrabold text-slate-100 font-mono">{report.total_samples}</p>
        </div>
        <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-500/30 space-y-1">
          <span className="text-[10px] font-mono uppercase text-amber-300 font-bold block">False Positives</span>
          <p className="text-2xl font-extrabold text-amber-300 font-mono">{fpPct}%</p>
          <p className="text-[10px] text-slate-400">{report.false_positives} samples</p>
        </div>
        <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 space-y-1">
          <span className="text-[10px] font-mono uppercase text-rose-300 font-bold block">False Negatives</span>
          <p className="text-2xl font-extrabold text-rose-300 font-mono">{fnPct}%</p>
          <p className="text-[10px] text-slate-400">{report.false_negatives} samples</p>
        </div>
      </div>

      {/* Sample-Level Comparison Table */}
      <div className="rounded-2xl overflow-hidden border border-slate-800">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-900/90 border-b border-slate-800">
              <th className="text-left px-4 py-3 font-mono text-slate-400 uppercase text-[10px]">Scenario</th>
              <th className="text-center px-3 py-3 font-mono text-slate-400 uppercase text-[10px]">Human Gold</th>
              <th className="text-center px-3 py-3 font-mono text-slate-400 uppercase text-[10px]">LLM Judge</th>
              <th className="text-center px-3 py-3 font-mono text-slate-400 uppercase text-[10px]">Agreed?</th>
              <th className="text-left px-3 py-3 font-mono text-slate-400 uppercase text-[10px]">Human Failure Category</th>
            </tr>
          </thead>
          <tbody>
            {report.samples.map((sample, i) => (
              <tr
                key={sample.id}
                className={`border-b border-slate-800/80 transition ${
                  i % 2 === 0 ? 'bg-slate-950' : 'bg-slate-900/40'
                } ${!sample.agreed ? 'ring-1 ring-rose-500/20' : ''}`}
              >
                <td className="px-4 py-2.5">
                  <p className="font-semibold text-slate-200 text-xs leading-tight line-clamp-1">
                    {sample.scenario_title}
                  </p>
                  <p className="text-[10px] text-slate-500 font-mono line-clamp-1 mt-0.5">
                    "{sample.trace_snippet}"
                  </p>
                </td>
                <td className="px-3 py-2.5 text-center">
                  {sample.gold_label_passed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 mx-auto" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400 mx-auto" />
                  )}
                </td>
                <td className="px-3 py-2.5 text-center">
                  {sample.judge_label_passed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 mx-auto" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400 mx-auto" />
                  )}
                </td>
                <td className="px-3 py-2.5 text-center">
                  {sample.agreed ? (
                    <span className="text-emerald-400 font-bold text-[11px]">✓ YES</span>
                  ) : (
                    <span className="text-rose-400 font-bold text-[11px] animate-pulse">✗ MISMATCH</span>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                    {sample.gold_failure_category || '—'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
