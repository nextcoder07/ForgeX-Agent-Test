import React from 'react';
import type { ExecutionTrace } from '../api/client';
import {
  Clock,
  Terminal,
  Cpu,
  Wrench,
  ShieldAlert,
  ArrowRight,
  Database,
  Mail,
  Zap,
  CheckCircle2,
} from 'lucide-react';

interface LiveExecutionTimelineProps {
  trace: ExecutionTrace;
}

export const LiveExecutionTimeline: React.FC<LiveExecutionTimelineProps> = ({ trace }) => {
  return (
    <div className="space-y-4">
      {/* Header Info */}
      <div className="p-4 rounded-xl glass-card border border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-cyan-500/20 text-cyan-400">
            <Terminal className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h4 className="text-xs font-bold text-slate-100 font-mono">Trace: {trace.id}</h4>
              {trace.is_counterfactual && (
                <span className="px-2 py-0.2 text-[9px] font-mono rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  COUNTERFACTUAL CONTROL
                </span>
              )}
            </div>
            <p className="text-[10px] text-slate-400">
              Agent: {trace.agent_id} ({trace.agent_version}) · Scenario: {trace.scenario_id}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-4 text-xs font-mono">
          <div>
            <span className="text-[10px] text-slate-500 uppercase block">Total Latency</span>
            <span className="text-cyan-300 font-bold">{trace.total_latency_ms} ms</span>
          </div>
          <div>
            <span className="text-[10px] text-slate-500 uppercase block">Tool Invocations</span>
            <span className="text-indigo-300 font-bold">{trace.tool_calls.length}</span>
          </div>
        </div>
      </div>

      {/* Sequential Event Timeline */}
      <div className="space-y-2 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-slate-800">
        {trace.events.map((evt, idx) => {
          const isUser = evt.role === 'user';
          const isThought = evt.role === 'agent_thought';
          const isToolCall = evt.role === 'tool_call';
          const isToolResult = evt.role === 'tool_result';
          const isAgentMsg = evt.role === 'agent_message';

          return (
            <div key={idx} className="relative flex items-start space-x-3 pl-8">
              {/* Timeline marker node */}
              <div
                className={`absolute left-2 top-1.5 w-3.5 h-3.5 rounded-full border-2 bg-slate-950 flex items-center justify-center ${
                  isUser
                    ? 'border-cyan-400'
                    : isThought
                    ? 'border-indigo-400'
                    : isToolCall
                    ? 'border-amber-400'
                    : isToolResult
                    ? 'border-emerald-400'
                    : 'border-slate-400'
                }`}
              />

              {/* Event Bubble */}
              <div className="flex-1 p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span
                    className={`font-mono text-[10px] uppercase font-bold ${
                      isUser
                        ? 'text-cyan-400'
                        : isThought
                        ? 'text-indigo-400'
                        : isToolCall
                        ? 'text-amber-400'
                        : isToolResult
                        ? 'text-emerald-400'
                        : 'text-slate-300'
                    }`}
                  >
                    {evt.role.replace('_', ' ')}
                  </span>
                  <span className="text-[9px] font-mono text-slate-500">
                    {evt.timestamp ? evt.timestamp.split('T')[1]?.slice(0, 8) : '12:00:00'}
                  </span>
                </div>

                <p className="text-slate-200 font-mono text-[11px] leading-relaxed break-words">
                  {evt.content}
                </p>

                {/* Tool call details drawer */}
                {evt.tool_call && (
                  <div className="mt-2 p-2 rounded-lg bg-slate-900 border border-slate-800 font-mono text-[10px] space-y-1">
                    <div className="flex justify-between text-slate-400">
                      <span>Routing: {evt.tool_call.routing_decision}</span>
                      <span>Latency: {evt.tool_call.latency_ms} ms</span>
                    </div>
                    {evt.tool_call.injected_fault && (
                      <span className="px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-500/30 font-bold block">
                        FAULT INJECTED: {evt.tool_call.injected_fault}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* State Changes & Security Events Summary */}
      {(trace.state_changes.length > 0 || trace.security_events.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
          {trace.state_changes.length > 0 && (
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <span className="text-[10px] font-mono uppercase font-bold text-slate-400 flex items-center space-x-1">
                <Database className="w-3 h-3 text-cyan-400" />
                <span>State Changes ({trace.state_changes.length})</span>
              </span>
              {trace.state_changes.map((sc, i) => (
                <div key={i} className="text-[10px] font-mono p-2 rounded bg-slate-900 border border-slate-800/80">
                  <span className="text-cyan-300 font-bold">{sc.resource_type}:{sc.resource_id}</span>
                  <div className="text-slate-400">
                    {sc.field}: <span className="line-through text-slate-500">{String(sc.before_value)}</span> → <span className="text-emerald-400">{String(sc.after_value)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {trace.security_events.length > 0 && (
            <div className="p-3 rounded-xl bg-rose-950/20 border border-rose-500/40 space-y-2">
              <span className="text-[10px] font-mono uppercase font-bold text-rose-300 flex items-center space-x-1">
                <ShieldAlert className="w-3 h-3 text-rose-400" />
                <span>Security Events ({trace.security_events.length})</span>
              </span>
              {trace.security_events.map((se, i) => (
                <div key={i} className="text-[10px] font-mono p-2 rounded bg-rose-950/40 border border-rose-500/30 text-rose-200">
                  <div className="font-bold uppercase">{se.event_type} ({se.severity})</div>
                  <p className="text-[9px] text-rose-300/80">{se.evidence}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
