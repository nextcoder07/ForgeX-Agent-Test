import React, { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { DashboardPage } from './pages/DashboardPage';
import { AgentsPage } from './pages/AgentsPage';
import { ScenarioGeneratorPage } from './pages/ScenarioGeneratorPage';
import { DependencySetupPage } from './pages/DependencySetupPage';
import { ExecutionPage } from './pages/ExecutionPage';
import { ResultsPage } from './pages/ResultsPage';
import { ImprovePage } from './pages/ImprovePage';
import { PlatformAIPerformancePage } from './pages/PlatformAIPerformancePage';
import { AgentTesterBottomDrawer } from './components/AgentTesterBottomDrawer';
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
    <div className="min-h-screen bg-[#030712] text-slate-100 pb-12">
      <Navbar />
      <main className="pb-16">
        <Routes>
          {/* Root */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />

          {/* 1. Agents — contains intake, x-ray, and versions as tabs */}
          <Route path="/agents" element={<AgentsPage onAgentRegistered={handleAgentRegistered} />} />
          <Route path="/agents/:agentId" element={<AgentsPage onAgentRegistered={handleAgentRegistered} />} />

          {/* 2. Scenarios — contains generate, library, adversarial as tabs */}
          <Route path="/scenarios" element={<ScenarioGeneratorPage />} />

          {/* 3. Setup — contains AI model slots, services & credentials, sandbox as tabs */}
          <Route path="/setup" element={<DependencySetupPage agent={lastRegisteredAgent || undefined} />} />

          {/* 4. Execute — contains run + live telemetry tabs */}
          <Route path="/executions" element={<ExecutionPage />} />

          {/* 5. Results — contains scorecard, failures, calibration settings tabs */}
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/results/:jobId" element={<ResultsPage />} />

          {/* 6. Improve — contains failures, repairs, regression, model training tabs */}
          <Route path="/improve" element={<ImprovePage />} />
          <Route path="/improve/:jobId" element={<ImprovePage />} />

          {/* 7. Platform AI Quality Lab — self-evaluation & stage fallback training */}
          <Route path="/platform-ai" element={<PlatformAIPerformancePage />} />
          <Route path="/quality-lab" element={<PlatformAIPerformancePage />} />


          {/* ── Legacy redirects — don't break old links ── */}
          <Route path="/intake" element={<Navigate to="/agents?tab=intake" replace />} />
          <Route path="/dependencies" element={<Navigate to="/setup" replace />} />
          <Route path="/models" element={<Navigate to="/setup?tab=ai-models" replace />} />
          <Route path="/evaluations" element={<Navigate to="/results" replace />} />
          <Route path="/evaluations/:jobId" element={<Navigate to="/results" replace />} />
          <Route path="/diagnosis" element={<Navigate to="/improve?tab=failures" replace />} />
          <Route path="/diagnosis/:jobId" element={<Navigate to="/improve?tab=failures" replace />} />
          <Route path="/fix-agent" element={<Navigate to="/improve?tab=repairs" replace />} />
          <Route path="/regression" element={<Navigate to="/improve?tab=regression" replace />} />
          <Route path="/training" element={<Navigate to="/improve?tab=training" replace />} />
          <Route path="/live-attack" element={<Navigate to="/scenarios?tab=adversarial" replace />} />
          <Route path="/failures" element={<Navigate to="/improve?tab=failures" replace />} />
          <Route path="/failures/:jobId" element={<Navigate to="/improve?tab=failures" replace />} />
          <Route path="/scorecard" element={<Navigate to="/results?tab=failures" replace />} />
          <Route path="/calibration" element={<Navigate to="/results?tab=settings" replace />} />
          <Route path="/pipeline" element={<Navigate to="/executions?tab=telemetry" replace />} />

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
      <AgentTesterBottomDrawer currentAgent={lastRegisteredAgent} />
    </div>
  );
}

