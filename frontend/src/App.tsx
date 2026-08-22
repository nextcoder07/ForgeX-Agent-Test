import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import type { PageId } from './components/Navbar';
import { DashboardPage } from './pages/DashboardPage';
import { AgentIntakePage } from './pages/AgentIntakePage';
import { AgentsPage } from './pages/AgentsPage';
import { ScenarioGeneratorPage } from './pages/ScenarioGeneratorPage';
import { EvaluationRunPage } from './pages/EvaluationRunPage';
import { LiveAttackPage } from './pages/LiveAttackPage';
import { CalibrationPage } from './pages/CalibrationPage';
import { RegressionPage } from './pages/RegressionPage';
import { PipelineObservabilityPage } from './pages/PipelineObservabilityPage';
import type { AgentRecord } from './api/client';

export default function App() {
  const [activePage, setActivePage] = useState<PageId>('dashboard');
  const [lastRegisteredAgent, setLastRegisteredAgent] = useState<AgentRecord | null>(null);

  const navigate = (page: PageId) => setActivePage(page);

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard':
        return <DashboardPage onNavigate={navigate} />;
      case 'intake':
        return (
          <AgentIntakePage
            onNavigate={navigate}
            onAgentRegistered={(agent) => {
              setLastRegisteredAgent(agent);
            }}
          />
        );
      case 'agents':
        return <AgentsPage onNavigate={navigate} />;
      case 'scenarios':
        return <ScenarioGeneratorPage onNavigate={navigate} />;
      case 'evaluations':
        return <EvaluationRunPage onNavigate={navigate} />;
      case 'live-attack':
        return <LiveAttackPage />;
      case 'failures':
        return <EvaluationRunPage onNavigate={navigate} />;
      case 'scorecard':
        return <RegressionPage />;
      case 'calibration':
        return <CalibrationPage />;
      case 'pipeline':
        return <PipelineObservabilityPage />;
      default:
        return <DashboardPage onNavigate={navigate} />;
    }
  };

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100">
      <Navbar activePage={activePage} onNavigate={navigate} />
      <main className="pb-16">
        {renderPage()}
      </main>
    </div>
  );
}
