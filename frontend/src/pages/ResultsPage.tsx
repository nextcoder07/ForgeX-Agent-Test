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
  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4">
      <EvaluationRunPage />
    </div>
  );
};
