import React from 'react';
import { useNavigate, useParams } from "react-router-dom";
import { LiveAttackConsole } from '../components/LiveAttackConsole';
import { Flame } from 'lucide-react';
import { LiveProcessMonitor } from '../components/LiveProcessMonitor';

export const LiveAttackPage: React.FC = () => {
  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center space-x-2.5">
          <Flame className="w-5 h-5 sm:w-6 sm:h-6 text-rose-400" />
          <span>Live Red-Teaming Attack Console</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-300 mt-1">
          Fire real-time adversarial prompts at any registered agent. The platform simultaneously runs a counterfactual clean control and proves whether the attack caused the failure.
        </p>
      </div>

      <div className="p-3.5 sm:p-5 rounded-2xl glass-panel border border-slate-700/80 bg-slate-950/90 shadow-xl">
        <LiveAttackConsole />
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="p-3 sm:p-3.5 rounded-xl glass-card border border-rose-500/40 space-y-1.5">
          <h3 className="text-xs font-bold text-rose-300">Attack Scenario</h3>
          <p className="text-[11px] text-slate-300 leading-relaxed">
            Your prompt is sent to the agent running in an isolated sandbox. All tool calls are intercepted and logged without touching real systems.
          </p>
        </div>
        <div className="p-3 sm:p-3.5 rounded-xl glass-card border border-purple-500/40 space-y-1.5">
          <h3 className="text-xs font-bold text-purple-300">Counterfactual Replay</h3>
          <p className="text-[11px] text-slate-300 leading-relaxed">
            The platform strips adversarial patterns (authority claims, injection prefixes) and replays an identical clean conversation to isolate causation.
          </p>
        </div>
        <div className="p-3 sm:p-3.5 rounded-xl glass-card border border-emerald-500/40 space-y-1.5">
          <h3 className="text-xs font-bold text-emerald-300">Causation Proof</h3>
          <p className="text-[11px] text-slate-300 leading-relaxed">
            If the attack run fails but the clean control passes, causation is proven. If both fail, the agent has a pre-existing vulnerability.
          </p>
        </div>
      </div>

      {/* Live Process Monitor */}
      <LiveProcessMonitor />
    </div>
  );
};
