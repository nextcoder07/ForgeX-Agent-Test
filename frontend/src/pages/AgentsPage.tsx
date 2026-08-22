import React, { useState, useEffect } from 'react';
import { fetchAgents, fetchDemoAgentFiles } from '../api/client';
import type { AgentRecord } from '../api/client';
import { CodeFileInspector } from '../components/CodeFileInspector';
import { AgentMapGraph } from '../components/AgentMapGraph';
import {
  Cpu,
  RefreshCw,
  ChevronRight,
  Wrench,
  ShieldAlert,
  FileCode,
  Network,
  Layers,
  Sparkles,
} from 'lucide-react';
import type { PageId } from '../components/Navbar';

interface AgentsPageProps {
  onNavigate: (page: PageId) => void;
}

export const AgentsPage: React.FC<AgentsPageProps> = ({ onNavigate }) => {
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentRecord | null>(null);
  const [agentFiles, setAgentFiles] = useState<Record<string, string>>({});
  const [agentMeta, setAgentMeta] = useState<Record<string, string>>({});
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'files' | 'tools' | 'constitution' | 'map'>('files');

  useEffect(() => {
    fetchAgents()
      .then((list) => {
        setAgents(list);
        if (list.length > 0) {
          selectAgent(list[0]);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const selectAgent = async (agent: AgentRecord) => {
    setSelectedAgent(agent);
    setAgentFiles({});
    setAgentMeta({});
    setLoadingFiles(true);

    // Use source_files directly from the agent record if present
    if (agent.source_files && Object.keys(agent.source_files).length > 0) {
      setAgentFiles(agent.source_files);
      const entrypoint = agent.runtime_manifest?.entrypoint || 'agent.py';
      setAgentMeta({ entrypoint });
      setLoadingFiles(false);
      return;
    }

    // Try to load the underlying source files (works for demo agents)
    const localId = agent.id.replace('agent-', '').replace('-v1', '');
    try {
      const data = await fetchDemoAgentFiles(localId);
      if (data.files) setAgentFiles(data.files);
      if (data.metadata) setAgentMeta(data.metadata);
    } catch {
      // Not a local demo agent — normal registered agent
    } finally {
      setLoadingFiles(false);
    }
  };

  // Build graph nodes and edges from agent data for display
  const graphNodes = selectedAgent
    ? [
        { id: selectedAgent.id, label: selectedAgent.name, type: 'agent', risk: 'low', details: selectedAgent.description },
        ...selectedAgent.tools.map((t) => ({
          id: t.name,
          label: t.name,
          type: 'tool',
          risk: t.risk,
          details: t.description,
        })),
        ...selectedAgent.dependencies.map((d) => ({
          id: d.id,
          label: d.name,
          type: d.type as 'database' | 'api',
          risk: 'low',
          details: `${d.type} · required: ${d.required}`,
        })),
      ]
    : [];

  const graphEdges = selectedAgent
    ? [
        ...selectedAgent.tools.map((t) => ({ source: selectedAgent.id, target: t.name, label: 'calls' })),
        ...selectedAgent.dependencies.map((d) => ({ source: selectedAgent.id, target: d.id, label: 'depends on' })),
      ]
    : [];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">Agents & X-Ray Inspector</h1>
        <p className="text-sm text-slate-400 mt-1">
          View all registered agents. Inspect their source code, tool inventory, constitutional rules, and auto-discovered architecture map.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Agent Sidebar List */}
        <div className="lg:col-span-1 space-y-2">
          {loading ? (
            <div className="p-4 text-center text-xs text-slate-400">
              <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-1" />
              Loading agents...
            </div>
          ) : (
            agents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => selectAgent(agent)}
                className={`w-full p-3 rounded-xl text-left border transition-all ${
                  selectedAgent?.id === agent.id
                    ? 'bg-cyan-950/40 border-cyan-500/50 shadow-md'
                    : 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Cpu className={`w-3.5 h-3.5 ${selectedAgent?.id === agent.id ? 'text-cyan-400' : 'text-slate-500'}`} />
                    <span className="text-xs font-bold text-slate-100 truncate">{agent.display_name || agent.name}</span>
                  </div>
                  {selectedAgent?.id === agent.id && (
                    <ChevronRight className="w-3 h-3 text-cyan-400 shrink-0" />
                  )}
                </div>
                <p className="text-[10px] text-slate-400 font-mono mt-0.5 ml-5">Registered: {agent.name}</p>
                <div className="flex items-center space-x-2 mt-1 ml-5">
                  <span className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-indigo-950 text-indigo-300 border border-indigo-500/20">
                    {agent.version_label}
                  </span>
                  <span className="text-[9px] text-slate-500">{agent.tools.length} tools</span>
                </div>
                <p className="text-[9px] text-slate-600 font-mono mt-1 ml-5 truncate">{agent.domain} · {agent.id}</p>
              </button>
            ))
          )}

          <button
            onClick={() => onNavigate('intake')}
            className="w-full py-2 rounded-xl border border-dashed border-slate-700 text-xs text-slate-400 hover:border-cyan-500/50 hover:text-cyan-300 flex items-center justify-center space-x-1.5 transition"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Add New Agent</span>
          </button>
        </div>

        {/* Agent Inspector Main Panel */}
        <div className="lg:col-span-3 space-y-4">
          {selectedAgent ? (
            <>
              {/* Agent Header */}
              <div className="p-5 rounded-2xl glass-panel border border-slate-700 bg-gradient-to-r from-slate-950 via-indigo-950/20 to-slate-950 space-y-2">
                <div className="flex items-start justify-between flex-wrap gap-3">
                  <div>
                    <h2 className="text-lg font-extrabold text-slate-100">{selectedAgent.display_name || selectedAgent.name}</h2>
                    <p className="text-[11px] text-cyan-300 mt-0.5">Registered name: {selectedAgent.name}</p>
                    <p className="text-sm text-slate-400 mt-0.5">{selectedAgent.description}</p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="px-2.5 py-1 text-[10px] font-mono rounded-lg bg-indigo-950 text-indigo-300 border border-indigo-500/30">
                      {selectedAgent.version_label}
                    </span>
                    <span className="px-2.5 py-1 text-[10px] font-mono rounded-lg bg-slate-900 text-slate-400 border border-slate-700">
                      {selectedAgent.domain}
                    </span>
                  </div>
                </div>

                {/* Quick Stats */}
                <div className="flex items-center space-x-4 pt-2 border-t border-slate-800/80 text-[11px] font-mono text-slate-400">
                  <span>ID: <span className="text-cyan-300">{selectedAgent.id}</span></span>
                  <span>Tools: <span className="text-indigo-300">{selectedAgent.tools.length}</span></span>
                  <span>Deps: <span className="text-emerald-300">{selectedAgent.dependencies.length}</span></span>
                  <span>Goals: <span className="text-amber-300">{selectedAgent.constitution.goals.length}</span></span>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex space-x-1 border-b border-slate-800 overflow-x-auto">
                {(['files', 'tools', 'constitution', 'map'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-3 py-2 rounded-t-lg text-xs font-semibold transition whitespace-nowrap flex items-center space-x-1.5 ${
                      activeTab === tab
                        ? 'bg-slate-900 text-cyan-300 border border-b-0 border-slate-700'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {tab === 'files' && <FileCode className="w-3.5 h-3.5" />}
                    {tab === 'tools' && <Wrench className="w-3.5 h-3.5" />}
                    {tab === 'constitution' && <ShieldAlert className="w-3.5 h-3.5" />}
                    {tab === 'map' && <Network className="w-3.5 h-3.5" />}
                    <span className="capitalize">{tab === 'files' ? 'Source Files' : tab === 'map' ? 'Architecture Map' : tab}</span>
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div>
                {activeTab === 'files' && (
                  <div>
                    {loadingFiles ? (
                      <div className="py-12 text-center">
                        <RefreshCw className="w-5 h-5 text-cyan-400 animate-spin mx-auto" />
                        <p className="text-xs text-slate-400 mt-2">Loading source files...</p>
                      </div>
                    ) : Object.keys(agentFiles).length > 0 ? (
                      <CodeFileInspector files={agentFiles} metadata={agentMeta} />
                    ) : (
                      <div className="py-12 text-center text-slate-400 text-xs">
                        <FileCode className="w-8 h-8 mx-auto mb-2 text-slate-700" />
                        Source files not available for this agent. Use the Intake Engine to upload them.
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'tools' && (
                  <div className="space-y-3">
                    {selectedAgent.tools.map((tool, i) => (
                      <div key={i} className={`p-4 rounded-xl border glass-card space-y-2 ${
                        tool.risk === 'critical' ? 'border-rose-500/30' :
                        tool.risk === 'high' ? 'border-amber-500/30' :
                        'border-slate-800'
                      }`}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <Wrench className="w-4 h-4 text-slate-400" />
                            <span className="font-mono font-bold text-sm text-slate-100">{tool.name}</span>
                          </div>
                          <span className={`px-2 py-0.5 text-[9px] font-mono uppercase font-bold rounded border ${
                            tool.risk === 'critical' ? 'bg-rose-950 text-rose-300 border-rose-500/40' :
                            tool.risk === 'high' ? 'bg-amber-950 text-amber-300 border-amber-500/40' :
                            tool.risk === 'medium' ? 'bg-indigo-950 text-indigo-300 border-indigo-500/40' :
                            'bg-slate-800 text-slate-400 border-slate-700'
                          }`}>
                            {tool.risk} risk
                          </span>
                        </div>
                        <p className="text-xs text-slate-400">{tool.description}</p>
                        <div className="flex flex-wrap gap-2 text-[10px] font-mono">
                          {tool.is_destructive && (
                            <span className="px-1.5 py-0.5 rounded bg-rose-950/60 text-rose-400 border border-rose-500/30">DESTRUCTIVE</span>
                          )}
                          {tool.requires_confirmation && (
                            <span className="px-1.5 py-0.5 rounded bg-amber-950/60 text-amber-400 border border-amber-500/30">REQUIRES CONFIRM</span>
                          )}
                          {tool.canonical_capability && (
                            <span className="px-1.5 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-700">
                              canonical: {tool.canonical_capability}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {activeTab === 'constitution' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {([
                      ['Goals', selectedAgent.constitution.goals, 'text-cyan-300'],
                      ['Never Rules', selectedAgent.constitution.never_rules, 'text-rose-300'],
                      ['Always Rules', selectedAgent.constitution.always_rules, 'text-emerald-300'],
                      ['Escalation Rules', selectedAgent.constitution.escalation_rules, 'text-amber-300'],
                      ['Data Policies', selectedAgent.constitution.data_policies, 'text-indigo-300'],
                    ] as [string, string[], string][]).map(([title, items, color]) => (
                      <div key={title} className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                        <span className={`text-[10px] font-mono uppercase font-bold ${color}`}>{title}</span>
                        {items.length === 0 ? (
                          <p className="text-xs text-slate-500 italic">None defined.</p>
                        ) : (
                          <ul className="space-y-1">
                            {items.map((item, i) => (
                              <li key={i} className="text-xs text-slate-300 flex items-start space-x-1.5">
                                <span className={`${color} shrink-0 mt-0.5`}>›</span>
                                <span>{item}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {activeTab === 'map' && graphNodes.length > 0 && (
                  <AgentMapGraph nodes={graphNodes} edges={graphEdges} />
                )}
              </div>
            </>
          ) : (
            <div className="py-24 text-center text-slate-400">
              <Cpu className="w-12 h-12 mx-auto mb-4 text-slate-700" />
              <p className="text-sm">Select an agent from the left panel to inspect it.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
