import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from "react-router-dom";
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
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100">LLM Judge Calibration Benchmark</h1>
          <p className="text-xs sm:text-sm text-slate-300 mt-1">
            The AI judge's verdicts are compared against human gold-standard labels to compute agreement rate, false positive, and false negative rates.
          </p>
        </div>
        <button
          onClick={loadReport}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs text-slate-200 font-semibold flex items-center space-x-1.5 transition whitespace-nowrap"
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
