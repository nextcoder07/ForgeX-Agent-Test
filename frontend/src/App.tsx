import React, { useState } from 'react';
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
import { useEffect } from 'react';
import { ExecutionPage } from './pages/ExecutionPage';
import { FixMyAgentPage } from './pages/FixMyAgentPage';
import type { AgentRecord } from './api/client';

const getPageFromHash = (): PageId => {
  const hash = window.location.hash.slice(2);
  const validPages: PageId[] = [
    'dashboard',
    'intake',
    'dependencies',
    'agents',
    'scenarios',
    'executions',
    'evaluations',
    'fix-agent',
    'failures',
    'scorecard',
    'calibration',
    'pipeline',
  ];
  return validPages.includes(hash as PageId) ? (hash as PageId) : 'dashboard';
};

export default function App() {
  const [activePage, setActivePage] = useState<PageId>(getPageFromHash);
  const [activeEvaluationJobId, setActiveEvaluationJobId] = useState<string | undefined>(undefined);
  const [lastRegisteredAgent, setLastRegisteredAgent] = useState<AgentRecord | null>(() => {
    const saved = localStorage.getItem('lastRegisteredAgent');
    return saved ? JSON.parse(saved) : null;
  });

  useEffect(() => {
    const handleHashChange = () => {
      setActivePage(getPageFromHash());
    };
    window.addEventListener('hashchange', handleHashChange);

    // Sync initial hash if empty
    if (!window.location.hash) {
      window.location.hash = '#/' + activePage;
    }

    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (page: PageId) => {
    window.location.hash = '#/' + page;
    setActivePage(page);
  };

  const handleAgentRegistered = (agent: AgentRecord) => {
    setLastRegisteredAgent(agent);
    localStorage.setItem('lastRegisteredAgent', JSON.stringify(agent));
    navigate('dependencies');
  };

  const handleExecutionEvaluated = (evalJob: any) => {
    const jobId = evalJob?.id || evalJob?.job_id;
    if (jobId) {
      setActiveEvaluationJobId(jobId);
      // Navigate AFTER state is set so EvaluationRunPage gets the jobId immediately
      window.location.hash = '#/evaluations';
      setActivePage('evaluations');
    }
  };


  const renderPage = () => {
    switch (activePage) {
      case 'dashboard':
        return <DashboardPage onNavigate={navigate} />;
      case 'intake':
        return (
          <AgentIntakePage
            onNavigate={navigate}
            onAgentRegistered={handleAgentRegistered}
          />
        );
      case 'dependencies':
        return lastRegisteredAgent ? (
          <DependencySetupPage onNavigate={navigate} agent={lastRegisteredAgent} />
        ) : (
          <DashboardPage onNavigate={navigate} />
        );
      case 'agents':
        return <AgentsPage onNavigate={navigate} />;
      case 'scenarios':
        return <ScenarioGeneratorPage onNavigate={navigate} />;
      case 'executions':
        return (
          <ExecutionPage
            onNavigate={navigate}
            onExecutionEvaluated={handleExecutionEvaluated}
          />
        );
      case 'evaluations':
        return (
          <EvaluationRunPage
            onNavigate={navigate}
            evaluationJobId={activeEvaluationJobId}
          />
        );
      case 'fix-agent':
        return <FixMyAgentPage onNavigate={navigate} />;
      case 'live-attack':
        return <LiveAttackPage />;
      case 'failures':
        return (
          <EvaluationRunPage
            onNavigate={navigate}
            evaluationJobId={activeEvaluationJobId}
          />
        );
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
