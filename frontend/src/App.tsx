import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import type { PageId } from './components/Navbar';
import { DashboardPage } from './pages/DashboardPage';
import { AgentIntakePage } from './pages/AgentIntakePage';
import { DependencySetupPage } from './pages/DependencySetupPage';
import { AgentsPage } from './pages/AgentsPage';
import { ScenarioGeneratorPage } from './pages/ScenarioGeneratorPage';
import { EvaluationRunPage } from './pages/EvaluationRunPage';
import { LiveAttackPage } from './pages/LiveAttackPage';
import { CalibrationPage } from './pages/CalibrationPage';
import { RegressionPage } from './pages/RegressionPage';
import { PipelineObservabilityPage } from './pages/PipelineObservabilityPage';
import { ExecutionPage } from './pages/ExecutionPage';
import { FixMyAgentPage } from './pages/FixMyAgentPage';
import type { AgentRecord } from './api/client';

export default function App() {
  const [lastRegisteredAgent, setLastRegisteredAgent] = useState<AgentRecord | null>(() => {
    const saved = localStorage.getItem('lastRegisteredAgent');
    return saved ? JSON.parse(saved) : null;
  });

  const handleAgentRegistered = (agent: AgentRecord) => {
    setLastRegisteredAgent(agent);
    localStorage.setItem('lastRegisteredAgent', JSON.stringify(agent));
  };

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100">
      <Navbar />
      <main className="pb-16">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route 
            path="/intake" 
            element={<AgentIntakePage onAgentRegistered={handleAgentRegistered} />} 
          />
          <Route 
            path="/dependencies" 
            element={
              lastRegisteredAgent ? (
                <DependencySetupPage agent={lastRegisteredAgent} />
              ) : (
                <Navigate to="/dashboard" replace />
              )
            } 
          />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/scenarios" element={<ScenarioGeneratorPage />} />
          <Route path="/executions" element={<ExecutionPage />} />
          
          <Route path="/evaluations" element={<EvaluationRunPage />} />
          <Route path="/evaluations/:jobId" element={<EvaluationRunPage />} />
          
          <Route path="/fix-agent" element={<FixMyAgentPage />} />
          <Route path="/live-attack" element={<LiveAttackPage />} />
          
          <Route path="/failures" element={<EvaluationRunPage />} />
          <Route path="/failures/:jobId" element={<EvaluationRunPage />} />
          
          <Route path="/scorecard" element={<RegressionPage />} />
          <Route path="/calibration" element={<CalibrationPage />} />
          <Route path="/pipeline" element={<PipelineObservabilityPage />} />
          
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
