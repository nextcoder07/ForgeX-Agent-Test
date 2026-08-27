/**
 * ImprovePage — Stage 6
 * Consolidates: Diagnosis (Failures), Fix Agent (Repairs), Regression, Training Datasets
 * Maps legacy routes: /diagnosis, /fix-agent, /regression, /training
 */
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { Bug, Wrench, GitCompare, Database } from 'lucide-react';
import { DiagnosisPage } from './DiagnosisPage';
import { FixMyAgentPage } from './FixMyAgentPage';
import { RegressionPage } from './RegressionPage';
import { TrainingDatasetPage } from './TrainingDatasetPage';

export const ImprovePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = (searchParams.get('tab') || 'failures') as 'failures' | 'repairs' | 'regression' | 'training';

  const tabs = [
    { id: 'failures' as const, label: 'Failures & Diagnosis', icon: Bug },
    { id: 'repairs' as const, label: 'Repairs & Self-Healing', icon: Wrench },
    { id: 'regression' as const, label: 'Regression', icon: GitCompare },
    { id: 'training' as const, label: 'Model Training', icon: Database },
  ];

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4">
      {/* Page header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center space-x-2.5">
          <Wrench className="w-5 h-5 sm:w-6 sm:h-6 text-cyan-400" />
          <span>Improve</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Diagnose failures, apply repairs, run regression checks, and build training datasets.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex items-center space-x-1 border-b border-slate-800 flex-wrap">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setSearchParams({ tab: t.id })}
            className={`flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold rounded-t-lg border-b-2 transition-all cursor-pointer ${
              tab === t.id
                ? 'border-cyan-400 text-cyan-300 bg-slate-900/40'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/20'
            }`}
          >
            <t.icon className="w-3.5 h-3.5" />
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content — render full page components */}
      {tab === 'failures' && <DiagnosisPage />}
      {tab === 'repairs' && <FixMyAgentPage />}
      {tab === 'regression' && <RegressionPage />}
      {tab === 'training' && <TrainingDatasetPage />}
    </div>
  );
};
