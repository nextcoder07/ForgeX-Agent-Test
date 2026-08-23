import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from "react-router-dom";
import {
  Shield,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Key,
  Link2,
  Server,
  Database,
  Globe,
  Mail,
  Terminal,
  HardDrive,
  CreditCard,
  Search,
  MapPin,
  Users,
  GitBranch,
  Layers,
  ArrowRight,
  RefreshCw,
  Sparkles,
  ExternalLink,
  Cpu,
  Lock,
} from 'lucide-react';
import type { PageId } from '../components/Navbar';
import type {
  AgentRecord,
  AgentDependency,
  PlatformResource,
  DependencyBindingType,
} from '../api/client';
import {
  getAgentDependencies,
  getPlatformResources,
  getAgentBindings,
  updateAgentBindings,
  fetchAgents,
} from '../api/client';
import { LiveProcessMonitor } from '../components/LiveProcessMonitor';

// ── Icon mapping for capabilities ──────────────────────────────────────────

const CAPABILITY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  PYTHON_RUNTIME: Terminal,
  WEB_SEARCH: Search,
  BROWSER: Globe,
  DATABASE: Database,
  FILESYSTEM: HardDrive,
  EMAIL: Mail,
  NEWS_API: Globe,
  LOCATION_SERVICE: MapPin,
  IDENTITY: Users,
  PAYMENT: CreditCard,
  STORAGE: HardDrive,
  GIT: GitBranch,
  API_MOCK: Server,
};

const STATUS_CONFIG = {
  ready: {
    label: 'Platform Provided',
    color: 'emerald',
    bgClass: 'bg-emerald-950/40 border-emerald-500/30',
    textClass: 'text-emerald-400',
    iconBg: 'bg-emerald-500/20',
    icon: CheckCircle2,
  },
  user_credential_required: {
    label: 'User Credential Required',
    color: 'amber',
    bgClass: 'bg-amber-950/30 border-amber-500/30',
    textClass: 'text-amber-400',
    iconBg: 'bg-amber-500/20',
    icon: Key,
  },
  user_oauth_required: {
    label: 'OAuth Connection Required',
    color: 'indigo',
    bgClass: 'bg-indigo-950/30 border-indigo-500/30',
    textClass: 'text-indigo-400',
    iconBg: 'bg-indigo-500/20',
    icon: Link2,
  },
  unsupported: {
    label: 'Unsupported — Provide Test Endpoint',
    color: 'rose',
    bgClass: 'bg-rose-950/30 border-rose-500/30',
    textClass: 'text-rose-400',
    iconBg: 'bg-rose-500/20',
    icon: XCircle,
  },
};

interface DependencySetupPageProps {
  agent?: AgentRecord;
}

export const DependencySetupPage: React.FC<DependencySetupPageProps> = ({ agent: initialAgent }) => {
  const navigate = useNavigate();
  const [agentsList, setAgentsList] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>(initialAgent?.id || '');
  const [currentAgent, setCurrentAgent] = useState<AgentRecord | null>(initialAgent || null);
  
  const [dependencies, setDependencies] = useState<AgentDependency[]>([]);
  const [resources, setResources] = useState<PlatformResource[]>([]);
  const [bindings, setBindings] = useState<DependencyBindingType[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [userInputs, setUserInputs] = useState<Record<string, string>>({});
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Fetch agents list on mount
  useEffect(() => {
    fetchAgents().then(list => {
      setAgentsList(list);
      if (!selectedAgentId && list.length > 0) {
        setSelectedAgentId(list[0].id);
        setCurrentAgent(list[0]);
      } else if (selectedAgentId) {
        const found = list.find(a => a.id === selectedAgentId);
        if (found) setCurrentAgent(found);
      }
    }).catch(console.error);
  }, []);

  // Reload dependency data whenever selectedAgentId changes
  useEffect(() => {
    if (selectedAgentId) {
      const found = agentsList.find(a => a.id === selectedAgentId);
      if (found) setCurrentAgent(found);
      loadData(selectedAgentId);
    }
  }, [selectedAgentId]);

  const loadData = async (agentId: string) => {
    setLoading(true);
    try {
      const [deps, res, binds] = await Promise.all([
        getAgentDependencies(agentId),
        getPlatformResources(),
        getAgentBindings(agentId),
      ]);
      setDependencies(deps);
      setResources(res);
      setBindings(binds);
    } catch (e) {
      console.error('Failed to load dependency data:', e);
    } finally {
      setLoading(false);
    }
  };

  const getBindingForDep = (depName: string): DependencyBindingType | undefined => {
    return bindings.find(b => b.dependency_name === depName);
  };

  const getIconForDep = (dep: AgentDependency): React.ComponentType<{ className?: string }> => {
    // Try to match by type first
    const binding = getBindingForDep(dep.dependency_name);
    if (binding?.status === 'ready') {
      // Find matching platform resource capability
      for (const [cap, icon] of Object.entries(CAPABILITY_ICONS)) {
        if (dep.dependency_name.toUpperCase().includes(cap) || dep.dependency_type.toUpperCase().includes(cap)) {
          return icon;
        }
      }
    }
    const typeMap: Record<string, React.ComponentType<{ className?: string }>> = {
      runtime: Terminal,
      tool: Cpu,
      credential: Key,
      external_api: ExternalLink,
      database: Database,
      email: Mail,
      browser: Globe,
      payment: CreditCard,
      filesystem: HardDrive,
    };
    return typeMap[dep.dependency_type] || Server;
  };

  const handleUserInput = (depName: string, value: string) => {
    setUserInputs(prev => ({ ...prev, [depName]: value }));
  };

  const handleSaveBindings = async () => {
    if (!selectedAgentId) return;
    setSaving(true);
    try {
      // Update bindings that have user input
      const updatedBindings = bindings.map(b => {
        if (userInputs[b.dependency_name]) {
          return {
            ...b,
            user_value: userInputs[b.dependency_name],
            status: 'ready' as const,
            resolution_type: 'user_credential' as const,
          };
        }
        return b;
      });
      const result = await updateAgentBindings(selectedAgentId, updatedBindings);
      setBindings(result);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e) {
      console.error('Failed to save bindings:', e);
    } finally {
      setSaving(false);
    }
  };

  // Categorize bindings
  const runtimeBindings = bindings.filter(b => {
    const dep = dependencies.find(d => d.dependency_name === b.dependency_name);
    return dep?.dependency_type === 'runtime';
  });

  const platformReady = bindings.filter(b => {
    const dep = dependencies.find(d => d.dependency_name === b.dependency_name);
    return b.status === 'ready' && dep?.dependency_type !== 'runtime';
  });

  const userRequired = bindings.filter(b =>
    b.status === 'user_credential_required' || b.status === 'user_oauth_required'
  );

  const unsupported = bindings.filter(b => b.status === 'unsupported');

  const totalDeps = bindings.length;
  const resolvedDeps = bindings.filter(b => b.status === 'ready').length;
  const progressPct = totalDeps > 0 ? Math.round((resolvedDeps / totalDeps) * 100) : 0;

  if (loading && !currentAgent) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-4">
          <div className="relative">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-cyan-500 via-indigo-500 to-violet-500 p-0.5 mx-auto animate-pulse">
              <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
                <Shield className="w-7 h-7 text-cyan-400 animate-spin" />
              </div>
            </div>
          </div>
          <p className="text-sm text-slate-400 font-mono">Analyzing dependencies...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header & Agent Selector */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-cyan-500 via-indigo-500 to-violet-500 p-0.5">
              <div className="w-9 h-9 bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Shield className="w-5 h-5 text-cyan-400" />
              </div>
            </div>
            <div>
              <h1 className="text-2xl font-extrabold text-slate-100">Agent Dependency Setup</h1>
              <p className="text-xs text-slate-400 mt-0.5 font-mono">
                {currentAgent ? `${currentAgent.display_name || currentAgent.name} · ${currentAgent.id}` : 'Select an agent to inspect dependencies'}
              </p>
            </div>
          </div>

          {/* Agent Selection Dropdown */}
          <div className="flex items-center space-x-3">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Select Agent:</label>
            <select
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-100 text-xs font-mono rounded-xl px-3 py-2 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
            >
              {agentsList.map(a => (
                <option key={a.id} value={a.id}>
                  {a.display_name || a.name} ({a.id})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Info Banner */}
        <div className="p-4 rounded-2xl glass-panel border border-cyan-500/20 bg-cyan-950/10">
          <div className="flex items-start space-x-3">
            <Sparkles className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-slate-200 font-semibold">
                These are the external requirements detected from your agent.
              </p>
              <p className="text-xs text-slate-400 mt-1">
                We provide free sandbox/test resources for most requirements. For remaining requirements,
                provide your own test credentials below.
              </p>
            </div>
          </div>
        </div>

        {/* Sandbox Needs & Simulation Mechanics Description */}
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/60 space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-indigo-400" />
            Sandbox Needs & Simulation Mechanics
          </h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            The platform establishes an isolated virtual harness matching your agent's resource specifications.
            All intercepted tool invocations and network access are routed dynamically based on a <strong>priority resolution policy</strong>:
          </p>
          <ol className="list-decimal pl-5 space-y-1.5 text-xs text-slate-400 font-mono">
            <li>
              <strong className="text-emerald-400">Platform Sandbox (Priority 1)</strong>: Mapped to safe, local mock drivers (e.g. SQLite DB, synthetic email redirection) which require no configuration.
            </li>
            <li>
              <strong className="text-cyan-400">Free API Providers (Priority 2)</strong>: Mapped to free developer tier endpoints if available.
            </li>
            <li>
              <strong className="text-amber-400">User Credentials (Priority 3)</strong>: Used only when custom external resources are needed.
            </li>
          </ol>
        </div>

        {/* Explicit 3-Mode Execution Selection */}
        <div className="p-6 rounded-2xl glass-panel border border-cyan-500/30 bg-slate-950/80 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Layers className="w-5 h-5 text-cyan-400" />
              <h2 className="text-base font-extrabold text-slate-100">Select Execution Mode</h2>
            </div>
            <span className="px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-cyan-950 text-cyan-300 border border-cyan-500/30">
              TRANSPARENT FIDELITY
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Mode 1: Faithful */}
            <div className="p-4 rounded-xl glass-card border border-emerald-500/30 bg-emerald-950/10 flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">MODE 1 — FAITHFUL</span>
                  <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-emerald-500/20 text-emerald-300">Fidelity: HIGH</span>
                </div>
                <p className="text-xs font-semibold text-slate-200">Original Model Execution</p>
                <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                  Executes agent using original model & credentials (e.g. OpenAI GPT-5). Requires original API credentials.
                </p>
              </div>
              <div className="pt-2 border-t border-emerald-500/20 flex items-center justify-between text-[10px] font-mono text-emerald-400">
                <span>Model Substitution: NO</span>
                <span>Confidence: HIGH</span>
              </div>
            </div>

            {/* Mode 2: Compatible */}
            <div className="p-4 rounded-xl glass-card border border-amber-500/30 bg-amber-950/10 flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">MODE 2 — COMPATIBLE</span>
                  <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-amber-500/20 text-amber-300">Fidelity: MEDIUM</span>
                </div>
                <p className="text-xs font-semibold text-slate-200">Alternative Model Substitute</p>
                <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                  Tests agent workflow & tools under Google Gemini when original credential is unavailable.
                </p>
              </div>
              <div className="pt-2 border-t border-amber-500/20 flex items-center justify-between text-[10px] font-mono text-amber-400">
                <span>Model Substitution: YES</span>
                <span>Confidence: MEDIUM</span>
              </div>
            </div>

            {/* Mode 3: Simulation */}
            <div className="p-4 rounded-xl glass-card border border-indigo-500/30 bg-indigo-950/10 flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">MODE 3 — SIMULATION</span>
                  <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-indigo-500/20 text-indigo-300">Fidelity: TEST-SPECIFIC</span>
                </div>
                <p className="text-xs font-semibold text-slate-200">Deterministic MockLLM</p>
                <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                  Uses MockLLM for deterministic tool call, failure, timeout, and malformed response testing.
                </p>
              </div>
              <div className="pt-2 border-t border-indigo-500/20 flex items-center justify-between text-[10px] font-mono text-indigo-400">
                <span>Model Substitution: MOCK</span>
                <span>Confidence: TEST-SPECIFIC</span>
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* Progress Bar */}
      <div className="p-4 rounded-2xl glass-panel border border-slate-800">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-mono text-slate-400">DEPENDENCY RESOLUTION</span>
          <span className="text-xs font-mono text-slate-300">
            <span className="text-cyan-400">{resolvedDeps}</span>/{totalDeps} resolved
          </span>
        </div>
        <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500 transition-all duration-700 ease-out"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center space-x-4 text-[10px] font-mono">
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span className="text-slate-400">Platform Sandbox</span>
            </span>
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <span className="text-slate-400">User Required</span>
            </span>
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-rose-400" />
              <span className="text-slate-400">Unsupported</span>
            </span>
          </div>
          <span className="text-[10px] font-mono text-slate-500">{progressPct}%</span>
        </div>
      </div>

      {/* Runtime Section */}
      {runtimeBindings.length > 0 && (
        <section>
          <div className="flex items-center space-x-2 mb-3">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">Runtime</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {runtimeBindings.map(binding => {
              const dep = dependencies.find(d => d.dependency_name === binding.dependency_name);
              return (
                <div
                  key={binding.id}
                  className="p-4 rounded-xl glass-card border border-emerald-500/20 flex items-center space-x-3 group hover:border-emerald-500/40 transition-all duration-300"
                >
                  <div className="p-2 rounded-lg bg-emerald-500/20">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-100 truncate">
                      {binding.dependency_name}
                    </p>
                    <p className="text-[10px] text-emerald-400 font-mono">
                      ✓ Platform Provided
                    </p>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-500/30">
                    READY
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Platform-Provided Tools Section */}
      {platformReady.length > 0 && (
        <section>
          <div className="flex items-center space-x-2 mb-3">
            <Server className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
              Tools — Platform Sandbox Provided
            </h2>
            <span className="px-2 py-0.5 text-[9px] font-mono rounded bg-cyan-950 text-cyan-300 border border-cyan-500/30">
              {platformReady.length} FREE
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {platformReady.map(binding => {
              const dep = dependencies.find(d => d.dependency_name === binding.dependency_name);
              const Icon = dep ? getIconForDep(dep) : Server;
              // Find matching resource for provider name
              const matchedResource = resources.find(r => {
                const depNameUpper = binding.dependency_name.toUpperCase().replace(/\s+/g, '_');
                return depNameUpper.includes(r.capability) || r.capability.includes(depNameUpper);
              });
              return (
                <div
                  key={binding.id}
                  className="p-4 rounded-xl glass-card border border-emerald-500/15 hover:border-emerald-500/40 transition-all duration-300 group"
                >
                  <div className="flex items-start space-x-3">
                    <div className="p-2.5 rounded-lg bg-emerald-500/15 group-hover:bg-emerald-500/25 transition-colors">
                      <Icon className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-slate-100 truncate">
                        {binding.dependency_name}
                      </p>
                      <p className="text-[10px] text-slate-400 mt-0.5">
                        {matchedResource?.provider || 'Sandbox Environment'}
                      </p>
                      <div className="flex items-center space-x-2 mt-2">
                        <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-500/30">
                          ✓ READY
                        </span>
                        <span className="text-[9px] text-slate-500 font-mono">
                          {matchedResource?.mode || binding.resolution_type}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* User Credential Required Section */}
      {userRequired.length > 0 && (
        <section>
          <div className="flex items-center space-x-2 mb-3">
            <Key className="w-4 h-4 text-amber-400" />
            <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
              External APIs — User Credentials Required
            </h2>
            <span className="px-2 py-0.5 text-[9px] font-mono rounded bg-amber-950 text-amber-300 border border-amber-500/30">
              {userRequired.length} PENDING
            </span>
          </div>
          <div className="space-y-3">
            {userRequired.map(binding => {
              const dep = dependencies.find(d => d.dependency_name === binding.dependency_name);
              const statusCfg = STATUS_CONFIG[binding.status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.user_credential_required;
              const StatusIcon = statusCfg.icon;
              const hasInput = !!userInputs[binding.dependency_name]?.trim();
              return (
                <div
                  key={binding.id}
                  className={`p-5 rounded-xl glass-card border ${statusCfg.bgClass} hover:border-opacity-60 transition-all duration-300`}
                >
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="flex items-start space-x-3">
                      <div className={`p-2.5 rounded-lg ${statusCfg.iconBg}`}>
                        <StatusIcon className={`w-5 h-5 ${statusCfg.textClass}`} />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-slate-100">
                          {binding.dependency_name}
                        </p>
                        <p className={`text-[10px] font-mono mt-0.5 ${statusCfg.textClass}`}>
                          {statusCfg.label}
                        </p>
                        {dep && (
                          <p className="text-[10px] text-slate-500 mt-1">
                            Detected from: {dep.detected_from} · Type: {dep.dependency_type}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500" />
                        <input
                          type="password"
                          placeholder={binding.status === 'user_oauth_required' ? 'OAuth Token...' : 'API Key or Endpoint...'}
                          value={userInputs[binding.dependency_name] || ''}
                          onChange={e => handleUserInput(binding.dependency_name, e.target.value)}
                          className="pl-8 pr-3 py-2 w-64 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-100 font-mono focus:outline-none focus:border-cyan-500 transition-colors"
                        />
                      </div>
                      <button
                        className={`px-4 py-2 rounded-lg text-xs font-bold flex items-center space-x-1.5 transition-all ${hasInput
                            ? 'bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white shadow-lg shadow-amber-500/20'
                            : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                          }`}
                        disabled={!hasInput}
                      >
                        <Key className="w-3 h-3" />
                        <span>Connect</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Unsupported Section */}
      {unsupported.length > 0 && (
        <section>
          <div className="flex items-center space-x-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
              Unsupported — Custom Endpoints
            </h2>
          </div>
          <div className="space-y-3">
            {unsupported.map(binding => {
              const dep = dependencies.find(d => d.dependency_name === binding.dependency_name);
              const hasInput = !!userInputs[binding.dependency_name]?.trim();
              return (
                <div
                  key={binding.id}
                  className="p-5 rounded-xl glass-card border border-rose-500/20 hover:border-rose-500/40 transition-all duration-300"
                >
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="flex items-start space-x-3">
                      <div className="p-2.5 rounded-lg bg-rose-500/15">
                        <XCircle className="w-5 h-5 text-rose-400" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-slate-100">
                          {binding.dependency_name}
                        </p>
                        <p className="text-[10px] font-mono mt-0.5 text-rose-400">
                          No platform sandbox available
                        </p>
                        {dep && (
                          <p className="text-[10px] text-slate-500 mt-1">
                            Detected from: {dep.detected_from}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      <input
                        type="text"
                        placeholder="https://your-test-endpoint.com/api"
                        value={userInputs[binding.dependency_name] || ''}
                        onChange={e => handleUserInput(binding.dependency_name, e.target.value)}
                        className="px-3 py-2 w-72 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-100 font-mono focus:outline-none focus:border-rose-500 transition-colors"
                      />
                      <button
                        className={`px-4 py-2 rounded-lg text-xs font-bold flex items-center space-x-1.5 transition-all ${hasInput
                            ? 'bg-gradient-to-r from-rose-500 to-pink-600 hover:from-rose-400 hover:to-pink-500 text-white shadow-lg shadow-rose-500/20'
                            : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                          }`}
                        disabled={!hasInput}
                      >
                        <Link2 className="w-3 h-3" />
                        <span>Provide Test Endpoint</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* All Resolved Banner */}
      {userRequired.length === 0 && unsupported.length === 0 && (
        <div className="p-5 rounded-2xl glass-panel border border-emerald-500/30 bg-emerald-950/10 flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-emerald-500/20">
            <CheckCircle2 className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <p className="text-sm font-bold text-emerald-300">
              All dependencies resolved! No user credentials needed.
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              Every requirement has been matched to a platform-provided sandbox or mock resource.
            </p>
          </div>
        </div>
      )}

      {/* Footer Action Bar */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate("/intake")}
            className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition"
          >
            ← Back to Intake
          </button>
          {(userRequired.length > 0 || unsupported.length > 0) && (
            <button
              onClick={handleSaveBindings}
              disabled={saving}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold text-xs shadow-lg shadow-cyan-500/20 flex items-center space-x-2 transition disabled:opacity-50"
            >
              {saving ? (
                <><RefreshCw className="w-4 h-4 animate-spin" /><span>Saving...</span></>
              ) : (
                <><Shield className="w-4 h-4" /><span>Save Credentials</span></>
              )}
            </button>
          )}
        </div>

        {saveSuccess && (
          <span className="text-xs font-mono text-emerald-400 flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3" />
            <span>Bindings saved successfully</span>
          </span>
        )}

        <button
          onClick={() => navigate("/scenarios")}
          className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-600 hover:from-emerald-400 hover:to-cyan-500 text-white font-extrabold text-xs shadow-lg shadow-emerald-500/25 flex items-center space-x-2 transition-all hover:scale-[1.02] active:scale-95"
        >
          <Layers className="w-4 h-4" />
          <span>Save and Proceed to Scenarios</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Live Process Monitor */}
      <LiveProcessMonitor />
    </div>
  );
};
