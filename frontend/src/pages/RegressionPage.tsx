import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from "react-router-dom";
import { compareRegressions } from '../api/client';
import type { RegressionComparison } from '../api/client';
import { RegressionView } from '../components/RegressionView';
import { GitCompare, RefreshCw } from 'lucide-react';

export const RegressionPage: React.FC = () => {
  const [fromJobId, setFromJobId] = useState('eval-job-baseline');
  const [toJobId, setToJobId] = useState('eval-job-hardened');
  const [comparison, setComparison] = useState<RegressionComparison | null>(null);
  const [loading, setLoading] = useState(false);

  const handleCompare = async () => {
    setLoading(true);
    setComparison(null);
    try {
      const result = await compareRegressions(fromJobId, toJobId);
      setComparison(result);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Auto-load default comparison
    handleCompare();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100">Regression & Version Diff Engine</h1>
        <p className="text-xs sm:text-sm text-slate-300 mt-1">
          Compare two evaluation jobs to detect regressions before deploying agent updates. Shows safety/capability deltas and which failures were resolved or newly introduced.
        </p>
      </div>

      {/* Comparison Controls */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 flex flex-wrap items-end gap-4">
        <div>
          <label className="text-xs font-semibold text-slate-400 block mb-1">Baseline Job ID (From):</label>
          <input
            type="text"
            value={fromJobId}
            onChange={(e) => setFromJobId(e.target.value)}
            className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 font-mono text-xs focus:outline-none focus:border-indigo-500 transition w-56"
            placeholder="eval-job-baseline"
          />
        </div>

        <div className="flex items-end">
          <GitCompare className="w-5 h-5 text-slate-500 mb-3" />
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-400 block mb-1">Candidate Job ID (To):</label>
          <input
            type="text"
            value={toJobId}
            onChange={(e) => setToJobId(e.target.value)}
            className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 font-mono text-xs focus:outline-none focus:border-indigo-500 transition w-56"
            placeholder="eval-job-hardened"
          />
        </div>

        <button
          onClick={handleCompare}
          disabled={loading || !fromJobId || !toJobId}
          className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 hover:from-indigo-400 hover:to-violet-500 text-slate-100 font-bold text-sm shadow-lg shadow-indigo-500/20 flex items-center space-x-2 transition disabled:opacity-50"
        >
          {loading ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Comparing...</span>
            </>
          ) : (
            <>
              <GitCompare className="w-4 h-4" />
              <span>Compare Versions</span>
            </>
          )}
        </button>
      </div>

      {/* Comparison Result */}
      {comparison && <RegressionView comparison={comparison} />}

      {!comparison && !loading && (
        <div className="py-16 text-center space-y-3">
          <GitCompare className="w-12 h-12 mx-auto text-slate-700" />
          <p className="text-sm text-slate-400">Enter two evaluation job IDs and click Compare.</p>
          <p className="text-[11px] text-slate-500">The platform uses seeded demo data for the default comparison.</p>
        </div>
      )}
    </div>
  );
};
