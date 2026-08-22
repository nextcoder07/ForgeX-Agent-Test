import React, { useState, useEffect } from 'react';
import { fetchCalibrationReport } from '../api/client';
import type { CalibrationReport } from '../api/client';
import { CalibrationPanel } from '../components/CalibrationPanel';
import { RefreshCw, CheckCircle2 } from 'lucide-react';

export const CalibrationPage: React.FC = () => {
  const [report, setReport] = useState<CalibrationReport | null>(null);
  const [loading, setLoading] = useState(true);

  const loadReport = async () => {
    setLoading(true);
    try {
      const data = await fetchCalibrationReport();
      setReport(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReport();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100">LLM Judge Calibration Benchmark</h1>
          <p className="text-sm text-slate-400 mt-1">
            The AI judge's verdicts are compared against human gold-standard labels to compute agreement rate, false positive, and false negative rates. This ensures evaluation results are trustworthy.
          </p>
        </div>
        <button
          onClick={loadReport}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-sm text-slate-300 font-semibold flex items-center space-x-2 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : 'text-slate-400'}`} />
          <span>Refresh</span>
        </button>
      </div>

      {loading ? (
        <div className="py-24 text-center space-y-3">
          <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin mx-auto" />
          <p className="text-sm text-slate-400">Loading calibration benchmark data...</p>
        </div>
      ) : report ? (
        <CalibrationPanel report={report} />
      ) : (
        <div className="py-24 text-center">
          <p className="text-sm text-slate-400">Failed to load calibration data. Make sure the backend is running.</p>
        </div>
      )}
    </div>
  );
};
