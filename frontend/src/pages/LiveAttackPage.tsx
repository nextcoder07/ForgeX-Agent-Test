import React from 'react';
import { LiveAttackConsole } from '../components/LiveAttackConsole';
import { Flame } from 'lucide-react';
import { LiveProcessMonitor } from '../components/LiveProcessMonitor';

export const LiveAttackPage: React.FC = () => {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
          <Flame className="w-6 h-6 text-rose-400" />
          <span>Live Red-Teaming Attack Console</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Fire real-time adversarial prompts at any registered agent. The platform simultaneously runs a counterfactual clean control and proves whether the attack caused the failure — not a pre-existing bug.
        </p>
      </div>

      <div className="p-6 rounded-2xl glass-panel border border-slate-800 bg-slate-950/90 shadow-2xl">
        <LiveAttackConsole />
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-2xl glass-card border border-rose-500/20 space-y-2">
          <h3 className="text-xs font-bold text-rose-300">Attack Scenario</h3>
          <p className="text-[11px] text-slate-400">
            Your prompt is sent to the agent running in an isolated sandbox. All tool calls are intercepted and logged without touching real systems.
          </p>
        </div>
        <div className="p-4 rounded-2xl glass-card border border-purple-500/20 space-y-2">
          <h3 className="text-xs font-bold text-purple-300">Counterfactual Replay</h3>
          <p className="text-[11px] text-slate-400">
            The platform strips adversarial patterns (authority claims, injection prefixes) and replays an identical clean conversation to isolate causation.
          </p>
        </div>
        <div className="p-4 rounded-2xl glass-card border border-emerald-500/20 space-y-2">
          <h3 className="text-xs font-bold text-emerald-300">Causation Proof</h3>
          <p className="text-[11px] text-slate-400">
            If the attack run fails but the clean control passes, causation is proven. If both fail, the agent has a pre-existing vulnerability unrelated to your attack.
          </p>
        </div>
      </div>

      {/* Live Process Monitor */}
      <LiveProcessMonitor />
    </div>
  );
};
