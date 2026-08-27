import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from "react-router-dom";
import { fetchAgents } from '../api/client';
import type { AgentRecord } from '../api/client';
import { PipelineMonitor } from '../components/PipelineMonitor';
import { PipelineSequenceTracker } from '../components/PipelineSequenceTracker';
import { LiveProcessMonitor } from '../components/LiveProcessMonitor';
import { Radio, Activity, Boxes, Play, ShieldCheck, Cpu, ArrowRight } from 'lucide-react';

export const PipelineObservabilityPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const agentIdFromUrl = queryParams.get('agentId');

  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const activeRunId = localStorage.getItem('lastPipelineRunId');

  useEffect(() => {
    fetchAgents().then(list => {
      setAgents(list);
      if (agentIdFromUrl && list.some(a => a.id === agentIdFromUrl)) {
        setSelectedAgentId(agentIdFromUrl);
      } else if (list.length > 0) {
        setSelectedAgentId(list[0].id);
      }
    });
  }, [agentIdFromUrl]);

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center space-x-2.5">
          <Radio className="w-5 h-5 sm:w-6 sm:h-6 text-cyan-400" />
          <span>Agent Perfection Pipeline Telemetry</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-300 mt-1">
          Complete end-to-end 9-stage telemetry hub. Follow your agent from Intake and Scenarios to Evaluation, Autonomous Code Repair, and Model Training.
        </p>
      </div>

      {/* Target Agent Selector */}
      {agents.length > 0 && (
        <div className="p-4 rounded-2xl glass-panel border border-slate-700/80 flex flex-wrap items-center justify-between gap-3">
          <div className="flex-1 min-w-64">
            <label className="text-xs font-semibold text-slate-300 block mb-1">Select Target Agent for Pipeline Telemetry:</label>
            <select
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              className="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-700 text-cyan-300 font-mono text-xs focus:outline-none focus:border-cyan-500 transition"
            >
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name || a.name} · registered: {a.name} · {a.version_label}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => navigate(`/intake`)}
            className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 text-xs font-bold font-mono flex items-center gap-1.5 transition"
          >
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            <span>Intake New Agent</span>
          </button>
        </div>
      )}

      {/* Dedicated Full 9-Stage Perfection Architecture Tracker */}
      {selectedAgentId && (
        <div className="space-y-2">
          <div className="text-[11px] font-mono font-bold uppercase text-slate-300 tracking-wider px-1">
            9-Stage Lifecycle Progress & Prerequisites:
          </div>
          <PipelineSequenceTracker agentId={selectedAgentId} currentStageId="pipeline" />
        </div>
      )}

      {/* Active Run Telemetry Stream */}
      {activeRunId && (
        <PipelineMonitor runId={activeRunId} />
      )}

      {/* 9-Stage Architecture Architecture Map */}
      <div className="p-4 sm:p-5 rounded-2xl glass-panel border border-slate-700/80 space-y-3">
        <h2 className="text-xs sm:text-sm font-bold text-slate-100 flex items-center space-x-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span>Perfection Pipeline Workflow</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { label: '1. Intake & Risk Scenarios', desc: 'Reconstruct AST interfaces, dependencies, and generate multi-category test suites.', icon: Boxes, color: 'border-cyan-500/40 text-cyan-300' },
            { label: '2. Sandbox & Real Evaluation', desc: 'Execute live subprocess/HTTP calls in isolated sandboxes and compute composite scorecards.', icon: Activity, color: 'border-emerald-500/40 text-emerald-300' },
            { label: '3. Autonomous Fix & Fine-Tuning', desc: 'Diagnose failure roots, review AST patch diffs, and train DPO/LoRA adapters.', icon: ShieldCheck, color: 'border-indigo-500/40 text-indigo-300' },
          ].map((stage) => (
            <div key={stage.label} className={`p-3.5 rounded-xl glass-card border ${stage.color.split(' ')[0]} space-y-1`}>
              <div className="flex items-center gap-2"><stage.icon className={`w-3.5 h-3.5 ${stage.color.split(' ')[1]}`} /><span className={`text-[10px] font-bold font-mono uppercase ${stage.color.split(' ')[1]}`}>{stage.label}</span></div>
              <p className="text-[11px] text-slate-300 leading-relaxed">{stage.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Live Process & Red-Teaming Monitor */}
      <LiveProcessMonitor />
    </div>
  );
};
