import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  Sparkles,
  Layers,
  Server,
  Radio,
  Zap,
  Wrench,
  Flame,
  Bug,
  Database,
  GitCompare,
  ShieldCheck,
  ChevronDown,
  LogOut,
  Trash2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Sidebar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, deleteAccount } = useAuth();
  const [profileOpen, setProfileOpen] = useState(false);

  const currentPath = location.pathname.split('/')[1] || 'dashboard';
  const currentTab = new URLSearchParams(location.search).get('tab');

  const mainNav = [
    { id: 'dashboard', label: 'Dashboard / Home', icon: Activity, path: '/dashboard' },
  ];

  const pipelineNav = [
    { id: 'agents', label: '1. Agents & AST Intake', icon: Sparkles, path: '/agents' },
    { id: 'scenarios', label: '2. Scenario Intelligence', icon: Layers, path: '/scenarios' },
    { id: 'setup', label: '3. Setup & Controls', icon: Server, path: '/setup' },
    { id: 'executions', label: '4. Sandboxed Execution', icon: Radio, path: '/executions' },
    { id: 'results', label: '5. Reliability Results', icon: Zap, path: '/results' },
    { id: 'improve', label: '6. Self-Healing & Improve', icon: Wrench, path: '/improve' },
  ];

  const safetyNav = [
    { id: 'red-teaming', label: 'Red-Teaming Attack', icon: Flame, path: '/scenarios?tab=adversarial', activeIf: currentPath === 'scenarios' && currentTab === 'adversarial' },
    { id: 'failures', label: 'Failures & Diagnosis', icon: Bug, path: '/improve?tab=failures', activeIf: currentPath === 'improve' && currentTab === 'failures' },
    { id: 'datasets', label: 'SFT/DPO Datasets', icon: Database, path: '/improve?tab=training', activeIf: currentPath === 'improve' && currentTab === 'training' },
    { id: 'regression', label: 'Regression Check', icon: GitCompare, path: '/improve?tab=regression', activeIf: currentPath === 'improve' && currentTab === 'regression' },
  ];

  const handleSignOut = async () => {
    await logout();
    navigate('/login');
  };

  const handleDeleteAccount = async () => {
    if (window.confirm('Are you sure you want to delete your account and all data?')) {
      await deleteAccount();
      navigate('/signup');
    }
  };

  return (
    <aside className="w-64 h-screen sticky top-0 bg-[#020617] border-r border-slate-800/80 flex flex-col justify-between z-40 font-mono text-xs select-none shrink-0 hidden md:flex">
      
      {/* Top Header & Workspace Switcher */}
      <div className="p-4 space-y-4">
        {/* Workspace Brand Box */}
        <div className="flex items-center space-x-2.5 p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 shadow-sm">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-500 via-indigo-500 to-rose-500 p-0.5 shrink-0">
            <div className="w-full h-full bg-slate-950 rounded-[6px] flex items-center justify-center">
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
            </div>
          </div>
          <span className="font-extrabold text-slate-100 tracking-tight text-xs font-mono">
            <span className="text-cyan-400">FORGE</span>X AGENTS
          </span>
        </div>

        {/* Navigation Sections */}
        <div className="space-y-4 pt-1 overflow-y-auto max-h-[calc(100vh-220px)] custom-scrollbar pr-1">
          
          {/* Main Home */}
          <div className="space-y-1">
            {mainNav.map(item => {
              const Icon = item.icon;
              const isActive = currentPath === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => navigate(item.path)}
                  className={`w-full px-3 py-2 rounded-xl text-left font-semibold flex items-center space-x-2.5 transition cursor-pointer ${
                    isActive
                      ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>

          {/* Group 1: Evaluation Pipeline */}
          <div className="space-y-1">
            <span className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
              Evaluation & Pipeline
            </span>
            {pipelineNav.map(item => {
              const Icon = item.icon;
              const isActive = currentPath === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => navigate(item.path)}
                  className={`w-full px-3 py-2 rounded-xl text-left font-semibold flex items-center space-x-2.5 transition cursor-pointer ${
                    isActive
                      ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </div>

          {/* Group 2: Safety & Compliance */}
          <div className="space-y-1">
            <span className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
              Safety & Red-Teaming
            </span>
            {safetyNav.map(item => {
              const Icon = item.icon;
              const isActive = item.activeIf;
              return (
                <button
                  key={item.id}
                  onClick={() => navigate(item.path)}
                  className={`w-full px-3 py-2 rounded-xl text-left font-semibold flex items-center space-x-2.5 transition cursor-pointer ${
                    isActive
                      ? 'bg-indigo-950/80 text-indigo-300 border border-indigo-500/40 shadow-sm shadow-indigo-500/10'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-400' : 'text-slate-500'}`} />
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Bottom User Account Footer */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/60 relative">
        {user ? (
          <div>
            <button
              onClick={() => setProfileOpen(!profileOpen)}
              className="w-full p-2 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center justify-between text-left hover:border-slate-700 transition cursor-pointer"
            >
              <div className="flex items-center space-x-2.5 truncate">
                {user.photoURL ? (
                  <img src={user.photoURL} alt="Avatar" className="w-6 h-6 rounded-full object-cover border border-cyan-500/40" />
                ) : (
                  <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-cyan-500 to-indigo-500 flex items-center justify-center font-bold text-slate-950 text-[10px]">
                    {user.displayName ? user.displayName.charAt(0).toUpperCase() : (user.email ? user.email.charAt(0).toUpperCase() : 'U')}
                  </div>
                )}
                <div className="truncate">
                  <p className="text-[11px] font-bold text-slate-200 truncate">{user.displayName || 'ForgeX Developer'}</p>
                  <p className="text-[9px] text-slate-400 truncate">{user.email}</p>
                </div>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            </button>

            {profileOpen && (
              <div className="absolute bottom-16 left-3 right-3 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl p-2 z-50 animate-fadeIn space-y-1">
                <button
                  onClick={handleSignOut}
                  className="w-full px-2.5 py-2 rounded-xl text-left text-xs font-semibold text-slate-300 hover:bg-slate-800 hover:text-white flex items-center space-x-2 transition cursor-pointer"
                >
                  <LogOut className="w-3.5 h-3.5 text-slate-400" />
                  <span>Sign Out</span>
                </button>
                <button
                  onClick={handleDeleteAccount}
                  className="w-full px-2.5 py-2 rounded-xl text-left text-xs font-semibold text-rose-400 hover:bg-rose-950/40 hover:text-rose-300 flex items-center space-x-2 transition cursor-pointer border-t border-slate-800 pt-2"
                >
                  <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                  <span>Delete Account</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <button
            onClick={() => navigate('/login')}
            className="w-full py-2 rounded-xl bg-cyan-500 text-slate-950 font-bold text-xs shadow transition cursor-pointer"
          >
            Sign In
          </button>
        )}
      </div>
    </aside>
  );
};
