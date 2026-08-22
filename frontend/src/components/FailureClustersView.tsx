import React, { useState } from 'react';
import type { FailureCluster } from '../api/client';
import {
  ShieldAlert,
  ChevronDown,
  ChevronRight,
  Wrench,
  AlertTriangle,
  Cpu,
  Layers,
  RefreshCw,
} from 'lucide-react';

interface FailureClustersViewProps {
  clusters: FailureCluster[];
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-rose-950 text-rose-300 border-rose-500/40',
  high: 'bg-amber-950 text-amber-300 border-amber-500/40',
  medium: 'bg-indigo-950 text-indigo-300 border-indigo-500/40',
  low: 'bg-slate-800 text-slate-400 border-slate-700',
};

export const FailureClustersView: React.FC<FailureClustersViewProps> = ({ clusters }) => {
  const [expandedId, setExpandedId] = useState<string | null>(
    clusters.length > 0 ? clusters[0].id : null
  );

  if (clusters.length === 0) {
    return (
      <div className="p-8 rounded-2xl glass-panel border border-emerald-500/30 text-center space-y-2">
        <ShieldAlert className="w-8 h-8 text-emerald-400 mx-auto" />
        <p className="text-sm font-bold text-emerald-300">No Failure Clusters Detected</p>
        <p className="text-xs text-slate-400">Agent passed all evaluated scenarios without clustering failure patterns.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {clusters.map((cluster) => {
        const isExpanded = expandedId === cluster.id;
        const severityStyle = SEVERITY_STYLES[cluster.severity] || SEVERITY_STYLES.low;

        return (
          <div
            key={cluster.id}
            className={`rounded-2xl border glass-card overflow-hidden transition-all ${
              isExpanded ? 'border-slate-700 shadow-lg' : 'border-slate-800'
            }`}
          >
            {/* Cluster Header */}
            <button
              onClick={() => setExpandedId(isExpanded ? null : cluster.id)}
              className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-900/50 transition"
            >
              <div className="flex items-center space-x-3">
                <span className={`px-2.5 py-1 text-[10px] font-mono uppercase font-bold rounded border ${severityStyle}`}>
                  {cluster.severity}
                </span>
                <div>
                  <h4 className="text-sm font-bold text-slate-100">{cluster.label}</h4>
                  <p className="text-[10px] font-mono text-slate-400">
                    {cluster.count} runs · Category: {cluster.category}
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <span className="text-[10px] font-mono text-slate-400 hidden md:block">
                  {cluster.member_verdict_ids.length} verdict(s) in cluster
                </span>
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                )}
              </div>
            </button>

            {/* Expanded Cluster Details */}
            {isExpanded && (
              <div className="px-4 pb-4 space-y-4 border-t border-slate-800">
                <div className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Evidence */}
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                    <span className="text-[10px] font-bold uppercase text-slate-400 flex items-center space-x-1.5">
                      <AlertTriangle className="w-3 h-3 text-rose-400" />
                      <span>Representative Evidence</span>
                    </span>
                    <p className="text-xs text-rose-200 font-mono italic leading-relaxed">
                      "{cluster.representative_evidence}"
                    </p>
                  </div>

                  {/* Recommended Fix */}
                  <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 space-y-2">
                    <span className="text-[10px] font-bold uppercase text-emerald-400 flex items-center space-x-1.5">
                      <Wrench className="w-3 h-3 text-emerald-400" />
                      <span>Recommended Remediation</span>
                    </span>
                    <p className="text-xs text-emerald-200 leading-relaxed">{cluster.recommended_fix}</p>
                  </div>
                </div>

                {/* Verdict ID Pills */}
                <div>
                  <span className="text-[10px] font-mono text-slate-500 block mb-1 uppercase">
                    Member Run Verdict IDs:
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {cluster.member_verdict_ids.map((vId) => (
                      <span key={vId} className="px-2 py-0.5 rounded-lg bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-400">
                        {vId}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
