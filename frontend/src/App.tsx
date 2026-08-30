import React, { useState } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { VerifyEmailPage } from './pages/VerifyEmailPage';
import { ProtectedRoute } from './components/ProtectedRoute';
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

function AppContent() {
  const { user } = useAuth();
  const location = useLocation();
  const [lastRegisteredAgent, setLastRegisteredAgent] = useState<AgentRecord | null>(() => {
    const saved = localStorage.getItem('lastRegisteredAgent');
    return saved ? JSON.parse(saved) : null;
  });

  // Remember current active route so browser refreshes stay on the exact same page
  React.useEffect(() => {
    const publicPaths = ['/', '/home', '/login', '/signup', '/verify-email'];
    if (!publicPaths.includes(location.pathname)) {
      sessionStorage.setItem('forgex_last_visited_path', location.pathname + location.search);
    }
  }, [location]);

  const getSavedPath = () => {
    const saved = sessionStorage.getItem('forgex_last_visited_path');
    return saved && saved !== '/' && saved !== '/login' ? saved : '/dashboard';
  };

  const handleAgentRegistered = (agent: AgentRecord) => {
    setLastRegisteredAgent(agent);
    localStorage.setItem('lastRegisteredAgent', JSON.stringify(agent));
  };

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 pb-12">
      <Navbar />
      <main className="pb-32">
        <Routes>
          {/* Public Landing & Authentication */}
          <Route path="/" element={user ? <Navigate to={getSavedPath()} replace /> : <HomePage />} />
          <Route path="/home" element={<HomePage />} />
          <Route path="/login" element={user?.emailVerified ? <Navigate to={getSavedPath()} replace /> : <LoginPage />} />
          <Route path="/signup" element={user?.emailVerified ? <Navigate to={getSavedPath()} replace /> : <SignupPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />

          {/* Protected Workspace Routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/agents"
            element={
              <ProtectedRoute>
                <AgentsPage onAgentRegistered={handleAgentRegistered} />
              </ProtectedRoute>
            }
          />
          <Route
            path="/agents/:agentId"
            element={
              <ProtectedRoute>
                <AgentsPage onAgentRegistered={handleAgentRegistered} />
              </ProtectedRoute>
            }
          />
          <Route
            path="/scenarios"
            element={
              <ProtectedRoute>
                <ScenarioGeneratorPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/setup"
            element={
              <ProtectedRoute>
                <DependencySetupPage agent={lastRegisteredAgent || undefined} />
              </ProtectedRoute>
            }
          />
          <Route
            path="/executions"
            element={
              <ProtectedRoute>
                <ExecutionPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/results"
            element={
              <ProtectedRoute>
                <ResultsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/results/:jobId"
            element={
              <ProtectedRoute>
                <ResultsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/improve"
            element={
              <ProtectedRoute>
                <ImprovePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/improve/:jobId"
            element={
              <ProtectedRoute>
                <ImprovePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/platform-ai"
            element={<Navigate to="/dashboard" replace />}
          />
          <Route
            path="/quality-lab"
            element={<Navigate to="/dashboard" replace />}
          />

          {/* ── Legacy redirects ── */}
          <Route path="/execution" element={<Navigate to="/executions" replace />} />
          <Route path="/scenario" element={<Navigate to="/scenarios" replace />} />
          <Route path="/agent" element={<Navigate to="/agents" replace />} />
          <Route path="/datasets" element={<Navigate to="/improve?tab=training" replace />} />
          <Route path="/dataset" element={<Navigate to="/improve?tab=training" replace />} />
          <Route path="/intake" element={<Navigate to="/agents?tab=register" replace />} />
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

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      {/* Agent Tester Subsystem temporarily turned off to prevent automated AI token consumption */}
      {/* Can be re-enabled whenever needed by toggling the flag below */}
      {false && user && <AgentTesterBottomDrawer currentAgent={lastRegisteredAgent} />}
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

