import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from "react-router-dom";
import { fetchAgents, deleteAgent } from '../api/client';
import type { AgentRecord } from '../api/client';
import { CodeFileInspector } from '../components/CodeFileInspector';
import { AgentMapGraph } from '../components/AgentMapGraph';
import { AgentIntakePage } from './AgentIntakePage';
import {
  Cpu,
  RefreshCw,
  Sparkles,
  Network,
  FileCode,
  Layers,
  Trash2,
  Plus,
  Wrench,
  ShieldAlert,
  ChevronRight,
} from 'lucide-react';

interface AgentsPageProps {
  onAgentRegistered?: (agent: AgentRecord) => void;
}

export const AgentsPage: React.FC<AgentsPageProps> = ({ onAgentRegistered }) => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  // Top-level tabs: Register (intake), Library (agent list + x-ray)
  const topTab = (searchParams.get('tab') || 'library') as 'register' | 'library';
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentRecord | null>(null);
  const [agentFiles, setAgentFiles] = useState<Record<string, string>>({});
  const [agentMeta, setAgentMeta] = useState<Record<string, string>>({});
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [activeTab, setActiveTab] = useState<'files' | 'tools' | 'constitution' | 'map'>('files');

  const handleAgentRegisteredInternal = (agent: AgentRecord) => {
    onAgentRegistered?.(agent);
    loadAgents();
    setSearchParams({ tab: 'library' });
  };

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = () => {
    setLoading(true);
    fetchAgents()
      .then((list) => {
        setAgents(list);
        if (list.length > 0) {
          selectAgent(list[0]);
        } else {
          setSelectedAgent(null);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  const handleDeleteAgent = async () => {
    if (!selectedAgent) return;
    const confirmDelete = window.confirm(
      `Are you sure you want to permanently delete agent "${selectedAgent.display_name || selectedAgent.name}" and all associated scenarios, files, execution traces, and databases?`
    );
    if (!confirmDelete) return;

    setDeleting(true);
    try {
      await deleteAgent(selectedAgent.id);
      loadAgents();
    } catch (err) {
      console.error('Failed to delete agent:', err);
      alert(`Failed to delete agent: ${err}`);
    } finally {
      setDeleting(false);
    }
  };

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

    // source_files not present — silently skip
    setLoadingFiles(false);
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
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100 flex items-center space-x-2.5">
            <Cpu className="w-5 h-5 sm:w-6 sm:h-6 text-cyan-400" />
            <span>Agents</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Register agents, inspect their architecture, and manage versions.
          </p>
        </div>
      </div>

      {/* Top tab bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-0 flex-wrap gap-2">
        <div className="flex items-center space-x-1">
          {([
            { id: 'library', label: 'Agent Library', icon: Layers },
            { id: 'register', label: '+ Register New Agent', icon: Plus },
          ] as const).map(tab => (
            <button
              key={tab.id}
              onClick={() => setSearchParams({ tab: tab.id })}
              className={`flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold rounded-t-lg border-b-2 transition-all cursor-pointer ${
                topTab === tab.id
                  ? 'border-cyan-400 text-cyan-300 bg-slate-900/40'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/20'
              }`}
            >
              <tab.icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        <button
          onClick={async () => {
            if (window.confirm("Purge all workspace data and delete all agents/scenarios/traces from disk?")) {
              try {
                const { purgeAllAgents } = await import('../api/client');
                await purgeAllAgents();
                loadAgents();
              } catch (e) {
                alert(`Purge failed: ${e}`);
              }
            }
          }}
          className="mb-1 px-3 py-1.5 rounded-lg border border-rose-500/30 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 font-mono text-[11px] font-bold flex items-center space-x-1 transition cursor-pointer"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span>Purge All Workspace Data</span>
        </button>
      </div>

      {/* Register tab — full AgentIntakePage embedded */}
      {topTab === 'register' && (
        <AgentIntakePage onAgentRegistered={handleAgentRegisteredInternal} />
      )}

      {/* Library tab — agent list + X-Ray panel */}
      {topTab === 'library' && (
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 lg:h-[calc(100vh-11rem)] lg:min-h-0">
        {/* Left Sidebar: Agent Selector */}
        <div className="flex min-h-0 flex-col gap-2">
          <div className="text-[10px] font-mono text-slate-300 uppercase tracking-wider px-1">
            Registered Agents ({agents.length})
          </div>

          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {loading ? (
              <div className="p-3 text-center text-xs text-slate-300">
                <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-1 text-cyan-400" />
                Loading agents...
              </div>
            ) : (
              agents.map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => selectAgent(agent)}
                  className={`w-full p-2.5 rounded-xl text-left border transition-all ${
                    selectedAgent?.id === agent.id
                      ? 'bg-cyan-950/60 border-cyan-500/60 shadow-md font-semibold'
                      : 'bg-slate-900/70 border-slate-700/80 hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2 min-w-0">
                      <Cpu className={`w-3.5 h-3.5 shrink-0 ${selectedAgent?.id === agent.id ? 'text-cyan-400' : 'text-slate-400'}`} />
                      <span className="text-xs font-bold text-slate-100 truncate">{agent.display_name || agent.name}</span>
                    </div>
                    {selectedAgent?.id === agent.id && (
                      <ChevronRight className="w-3 h-3 text-cyan-400 shrink-0" />
                    )}
                  </div>
                  <p className="text-[10px] text-slate-300 font-mono mt-0.5 ml-5">Registered: {agent.name}</p>
                  <div className="flex items-center space-x-2 mt-1 ml-5">
                    <span className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-indigo-950 text-indigo-300 border border-indigo-500/30">
                      {agent.version_label}
                    </span>
                    <span className="text-[9px] text-slate-300">{agent.tools.length} tools</span>
                  </div>
                  <p className="text-[9px] text-slate-400 font-mono mt-1 ml-5 truncate">{agent.domain} · {agent.id}</p>
                </button>
              ))
            )}
          </div>

          <button
            onClick={() => navigate("/intake")}
            className="w-full py-2 rounded-xl border border-dashed border-slate-700 text-xs text-slate-300 hover:border-cyan-500/60 hover:text-cyan-300 flex items-center justify-center space-x-1.5 transition"
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
              <div className="p-4 sm:p-5 rounded-2xl glass-panel border border-slate-700 bg-gradient-to-r from-slate-950 via-indigo-950/30 to-slate-950 space-y-2">
                <div className="flex items-start justify-between flex-wrap gap-3">
                  <div>
                    <h2 className="text-base sm:text-lg font-extrabold text-slate-100">{selectedAgent.display_name || selectedAgent.name}</h2>
                    <p className="text-[11px] text-cyan-300 mt-0.5">Registered name: {selectedAgent.name}</p>
                    <p className="text-xs sm:text-sm text-slate-300 mt-0.5">{selectedAgent.description}</p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="px-2.5 py-1 text-[10px] font-mono rounded-lg bg-indigo-950 text-indigo-300 border border-indigo-500/40">
                      {selectedAgent.version_label}
                    </span>
                    <span className="px-2.5 py-1 text-[10px] font-mono rounded-lg bg-slate-900 text-slate-400 border border-slate-700">
                      {selectedAgent.domain}
                    </span>
                    <button
                      onClick={handleDeleteAgent}
                      disabled={deleting}
                      className="px-2.5 py-1 text-[10px] font-mono font-bold rounded-lg bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-500/40 flex items-center space-x-1 transition disabled:opacity-50 cursor-pointer"
                      title="Permanently delete agent, files, and all test records from database"
                    >
                      <Trash2 className="w-3 h-3 text-rose-400" />
                      <span>{deleting ? 'Deleting...' : 'Delete Agent'}</span>
                    </button>
                  </div>
                </div>

                {/* Quick Stats */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-[11px] font-mono text-slate-400 flex-wrap gap-2">
                  <div className="flex items-center space-x-4">
                    <span>ID: <span className="text-cyan-300">{selectedAgent.id}</span></span>
                    <span>Tools: <span className="text-indigo-300">{selectedAgent.tools.length}</span></span>
                    <span>Deps: <span className="text-emerald-300">{selectedAgent.dependencies.length}</span></span>
                    <span>Goals: <span className="text-amber-300">{selectedAgent.constitution.goals.length}</span></span>
                  </div>
                  <button
                    onClick={() => navigate(`/scenarios?agentId=${selectedAgent.id}`)}
                    className="text-[10px] font-mono font-bold text-cyan-300 hover:text-cyan-200 flex items-center gap-1"
                  >
                    Generate Scenarios →
                  </button>
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
      )}
    </div>
  );
};
