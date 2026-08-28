import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield,
  Zap,
  Cpu,
  Layers,
  ArrowRight,
  CheckCircle2,
  Lock,
  Activity,
  Terminal,
  Play,
  RotateCw,
  Award,
  Sparkles,
  Search,
  ExternalLink
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const handleStart = () => {
    if (user) {
      navigate('/agents');
    } else {
      navigate('/signup');
    }
  };

  return (
    <div className="relative min-h-screen text-slate-100 selection:bg-cyan-500/30">
      {/* Ambient background glow elements */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[600px] overflow-hidden pointer-events-none -z-10">
        <div className="absolute -top-[200px] left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-gradient-to-tr from-cyan-600/15 via-indigo-600/20 to-purple-600/10 blur-[130px] rounded-full" />
        <div className="absolute top-[300px] right-[10%] w-[350px] h-[350px] bg-emerald-500/10 blur-[100px] rounded-full" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-24 space-y-24">
        {/* HERO SECTION */}
        <section className="text-center space-y-8 pt-6 sm:pt-12 max-w-4xl mx-auto">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-950/40 text-cyan-300 text-xs font-semibold backdrop-blur-md animate-fadeIn">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span>Autonomous AI Agent Reliability & Security Evaluation Platform</span>
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
          </div>

          {/* Main Title */}
          <h1 className="text-4xl sm:text-6xl font-black tracking-tight leading-[1.1] text-slate-100">
            Verify, Stress-Test & Harden{' '}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-indigo-300 to-purple-400">
              AI Agents
            </span>{' '}
            Before Production
          </h1>

          {/* Subtitle */}
          <p className="text-base sm:text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed">
            ForgeX automates the entire agent evaluation lifecycle: static AST intake, dynamic scenario generation, isolated sandboxed execution, 10-dimension reliability scorecards, and verifiable code repair.
          </p>

          {/* Call to Actions */}
          <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
            <button
              onClick={handleStart}
              className="px-6 py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-bold text-sm shadow-lg shadow-cyan-500/25 transition-all transform hover:-translate-y-0.5 flex items-center gap-2 cursor-pointer"
            >
              <span>{user ? 'Enter Platform Workspace' : 'Start Testing Free'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            {!user && (
              <button
                onClick={() => navigate('/login')}
                className="px-6 py-3.5 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-slate-700/60 text-slate-200 font-semibold text-sm transition-all flex items-center gap-2 cursor-pointer backdrop-blur-sm"
              >
                <span>Sign In to Account</span>
              </button>
            )}
          </div>

          {/* Key Metrics Ribbon */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-8 border-t border-slate-800/80 text-left">
            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 backdrop-blur-sm">
              <p className="text-2xl font-black text-cyan-400 font-mono">100%</p>
              <p className="text-xs text-slate-400 mt-0.5">Isolated Sandboxing</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 backdrop-blur-sm">
              <p className="text-2xl font-black text-indigo-400 font-mono">10</p>
              <p className="text-xs text-slate-400 mt-0.5">Evaluation Dimensions</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 backdrop-blur-sm">
              <p className="text-2xl font-black text-emerald-400 font-mono">6 Stages</p>
              <p className="text-xs text-slate-400 mt-0.5">Autonomous Pipeline</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 backdrop-blur-sm">
              <p className="text-2xl font-black text-purple-400 font-mono">Real-time</p>
              <p className="text-xs text-slate-400 mt-0.5">Adversarial Defense</p>
            </div>
          </div>
        </section>

        {/* 6-STAGE PIPELINE PREVIEW */}
        <section className="space-y-8">
          <div className="text-center space-y-2 max-w-2xl mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-100">
              The 6-Stage Agent Reliability Lifecycle
            </h2>
            <p className="text-xs sm:text-sm text-slate-400">
              A continuous loop from source code ingestion to audited patch promotion.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[
              {
                step: '01',
                title: 'AST Intake & Behavioral X-Ray',
                desc: 'Deep static code analysis extracting framework graphs, tools, secrets, and declared vs implemented policy invariants.',
                icon: Layers,
                color: 'text-cyan-400',
                border: 'hover:border-cyan-500/40',
              },
              {
                step: '02',
                title: 'Scenario Intelligence Engine',
                desc: 'Generates nominal, edge-case, and adversarial multi-turn test scenarios with LLM critic validation.',
                icon: Terminal,
                color: 'text-indigo-400',
                border: 'hover:border-indigo-500/40',
              },
              {
                step: '03',
                title: 'Dependency & Tool Gateway',
                desc: 'Auto-resolves model credentials, API endpoints, and sandbox mocks with faithful, compatible, or simulated execution modes.',
                icon: Lock,
                color: 'text-emerald-400',
                border: 'hover:border-emerald-500/40',
              },
              {
                step: '04',
                title: 'Sandboxed Trajectory Observer',
                desc: 'Executes agent runs in isolated child runtimes, recording step-by-step tool calls, security events, and output snapshots.',
                icon: Play,
                color: 'text-amber-400',
                border: 'hover:border-amber-500/40',
              },
              {
                step: '05',
                title: '10-Dimension Hybrid Evaluator',
                desc: 'Two-tier deterministic assertions and LLM judging to score safety, tool discipline, goal adherence, and robustness.',
                icon: Award,
                color: 'text-rose-400',
                border: 'hover:border-rose-500/40',
              },
              {
                step: '06',
                title: 'Root-Cause & Verifiable Repair',
                desc: 'Clusters failure signatures, runs counterfactual tests, generates unified diff patches, and verifies regression safety.',
                icon: RotateCw,
                color: 'text-purple-400',
                border: 'hover:border-purple-500/40',
              },
            ].map((st) => (
              <div
                key={st.step}
                className={`p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 transition-all duration-200 ${st.border} space-y-3 group backdrop-blur-sm`}
              >
                <div className="flex items-center justify-between">
                  <div className={`p-2.5 rounded-xl bg-slate-800/80 border border-slate-700/50 ${st.color}`}>
                    <st.icon className="w-5 h-5" />
                  </div>
                  <span className="text-xs font-mono font-bold text-slate-500">STAGE {st.step}</span>
                </div>
                <h3 className="text-base font-bold text-slate-100 group-hover:text-cyan-300 transition-colors">
                  {st.title}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {st.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* SECURITY & ISOLATION CALLOUT */}
        <section className="p-8 sm:p-12 rounded-3xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/20 space-y-6 text-center max-w-4xl mx-auto backdrop-blur-md">
          <div className="w-12 h-12 rounded-2xl bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center mx-auto text-indigo-300">
            <Shield className="w-6 h-6" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-100">
              Enterprise Multi-Tenant Security & Complete Isolation
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 max-w-xl mx-auto">
              Every user’s workspace is isolated. Your agent source code, credentials, test execution logs, and evaluation reports remain strictly confidential.
            </p>
          </div>
          <div className="pt-2">
            <button
              onClick={handleStart}
              className="px-7 py-3 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-sm shadow-md transition-all cursor-pointer"
            >
              Get Started with ForgeX
            </button>
          </div>
        </section>
      </div>
    </div>
  );
};
