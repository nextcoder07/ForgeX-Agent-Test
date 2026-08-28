/**
 * ResultsPage — Stage 5
 * Consolidates: 10D Scorecard, Failure Clusters, Root-Cause Diagnostics + Judge Calibration
 * Maps legacy routes: /evaluations, /calibration, /scorecard, /results
 */
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { Zap, Sliders } from 'lucide-react';
import { EvaluationRunPage } from './EvaluationRunPage';
import { CalibrationPage } from './CalibrationPage';

export const ResultsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = (searchParams.get('tab') || 'scorecard') as 'scorecard' | 'failures' | 'settings';

  const tabs = [
    { id: 'scorecard' as const, label: 'Scorecard & Failure Analysis', icon: Zap },
    { id: 'settings' as const, label: 'Judge Calibration & Settings', icon: Sliders },
  ];

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4">
      {/* Page header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center space-x-2.5">
          <Zap className="w-5 h-5 sm:w-6 sm:h-6 text-cyan-400 fill-current" />
          <span>Results & Reliability Scorecard</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Unified 10-dimension reliability scorecard, root-cause failure clustering, and judge calibration.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex items-center space-x-1 border-b border-slate-800">
        {tabs.map(t => {
          const isActive = (tab === 'failures' && t.id === 'scorecard') || tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setSearchParams({ tab: t.id })}
              className={`flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold rounded-t-lg border-b-2 transition-all cursor-pointer ${
                isActive
                  ? 'border-cyan-400 text-cyan-300 bg-slate-900/40'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/20'
              }`}
            >
              <t.icon className="w-3.5 h-3.5" />
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab content — Unified Scorecard + Failure Analysis or Settings */}
      {(tab === 'scorecard' || tab === 'failures') && <EvaluationRunPage />}
      {tab === 'settings' && <CalibrationPage />}
    </div>
  );
};
