import React from 'react';
import { Flame, ShieldAlert, Lock, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const LiveAttackPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-8 sm:py-12 space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center space-x-2.5">
          <Flame className="w-5 h-5 sm:w-6 sm:h-6 text-rose-400" />
          <span>Live Red-Teaming Attack Console</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-300 mt-1">
          Fire real-time adversarial prompts at any registered agent to test safety bounds and prompt injection resilience.
        </p>
      </div>

      {/* Temporarily Disabled Notice Banner */}
      <div className="p-8 sm:p-12 rounded-3xl glass-panel border border-rose-500/40 bg-slate-955/90 text-center space-y-5 shadow-2xl animate-fadeIn">
        <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/40 flex items-center justify-center mx-auto shadow-lg shadow-rose-500/10">
          <Lock className="w-8 h-8 text-rose-400" />
        </div>
        
        <div className="max-w-xl mx-auto space-y-2">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono font-bold uppercase tracking-wider mb-1">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Temporarily Disabled</span>
          </div>
          <h2 className="text-lg sm:text-xl font-black text-slate-100">
            Live Red-Teaming Attack Console is Currently Disabled
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
            The real-time adversarial attack console is temporarily offline while system maintenance and sandbox boundary hardening are in progress.
            All static scenario generation, execution verification, and 10-dimension evaluation features remain fully operational.
          </p>
        </div>

        <div className="pt-3 flex flex-wrap items-center justify-center gap-3">
          <button
            onClick={() => navigate('/scenarios?tab=generate')}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-extrabold text-xs shadow-lg shadow-cyan-500/20 flex items-center space-x-2 transition cursor-pointer"
          >
            <span>← Return to Scenario Generator</span>
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            className="px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-bold text-xs flex items-center space-x-2 transition cursor-pointer"
          >
            <span>Go to Dashboard</span>
          </button>
        </div>
      </div>
    </div>
  );
};
