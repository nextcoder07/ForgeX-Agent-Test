import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from "react-router-dom";
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
  Check,
  Zap,
  Play,
  Plus,
  Trash2,
  CheckCircle,
  FileCode,
  Info,
  Code,
} from 'lucide-react';
import type {
  AgentRecord,
  AgentDependency,
  PlatformResource,
  DependencyBindingType,
  SystemCredentialItem,
  SessionCredentialPrompt,
  ModelConnection,
  ModelConnectionTestResult,
} from '../api/client';
import {
  getAgentDependencies,
  getPlatformResources,
  getAgentBindings,
  updateAgentBindings,
  fetchAgents,
  getSystemCredentials,
  updateSystemCredentials,
  getAgentRequiredCredentials,
  listModelConnections,
  createModelConnection,
  updateModelConnection,
  testModelConnection,
  deleteModelConnection,
  getAgentModelBindings,
  updateAgentModelBindings,
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

const CURATED_MODELS_PER_PROVIDER: Record<string, { id: string; label: string; badge?: string }[]> = {
  gemini: [
    { id: 'gemini-2.5-flash', label: 'gemini-2.5-flash', badge: 'Fast / Rec' },
    { id: 'gemini-2.0-flash', label: 'gemini-2.0-flash' },
    { id: 'gemini-1.5-pro', label: 'gemini-1.5-pro', badge: 'Pro' },
    { id: 'gemini-3.6-flash', label: 'gemini-3.6-flash' },
  ],
  openai: [
    { id: 'gpt-4o-mini', label: 'gpt-4o-mini', badge: 'Fast / Rec' },
    { id: 'gpt-4o', label: 'gpt-4o', badge: 'Omni' },
    { id: 'o3-mini', label: 'o3-mini', badge: 'Reasoning' },
    { id: 'gpt-4-turbo', label: 'gpt-4-turbo' },
  ],
  anthropic: [
    { id: 'claude-3-5-sonnet-20241022', label: 'claude-3-5-sonnet', badge: 'Rec' },
    { id: 'claude-3-5-haiku-20241022', label: 'claude-3-5-haiku', badge: 'Fast' },
    { id: 'claude-3-opus-20240229', label: 'claude-3-opus' },
  ],
  openrouter: [
    { id: 'openai/gpt-4o-mini', label: 'openai/gpt-4o-mini', badge: 'Rec' },
    { id: 'anthropic/claude-3.5-sonnet', label: 'anthropic/claude-3.5-sonnet' },
    { id: 'meta-llama/llama-3.3-70b-instruct', label: 'meta-llama/llama-3.3-70b' },
    { id: 'deepseek/deepseek-r1', label: 'deepseek/deepseek-r1' },
    { id: 'google/gemini-2.0-flash-001', label: 'google/gemini-2.0-flash' },
  ],
  groq: [
    { id: 'llama-3.3-70b-versatile', label: 'llama-3.3-70b-versatile', badge: 'Rec' },
    { id: 'mixtral-8x7b-32768', label: 'mixtral-8x7b-32768' },
    { id: 'deepseek-r1-distill-llama-70b', label: 'deepseek-r1-distill-llama-70b' },
  ],
  deepseek: [
    { id: 'deepseek-chat', label: 'deepseek-chat', badge: 'V3 / Rec' },
    { id: 'deepseek-reasoner', label: 'deepseek-reasoner', badge: 'R1 Reasoning' },
  ],
};

interface SlotConfigState {
  mode: 'system_default' | 'cloud_api' | 'local_model';
  provider: string;
  base_url: string;
  model_identifier: string;
  api_key: string;
}

interface DependencySetupPageProps {
  agent?: AgentRecord;
}

export const DependencySetupPage: React.FC<DependencySetupPageProps> = ({ agent: initialAgent }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const agentIdFromUrl = queryParams.get('agentId');
  const isBlockedRedirect = queryParams.get('blocked') === 'true';
  const missingFromUrl = queryParams.get('missing');

  const [agentsList, setAgentsList] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>(initialAgent?.id || agentIdFromUrl || '');
  const [currentAgent, setCurrentAgent] = useState<AgentRecord | null>(initialAgent || null);
  
  const [dependencies, setDependencies] = useState<AgentDependency[]>([]);
  const [resources, setResources] = useState<PlatformResource[]>([]);
  const [bindings, setBindings] = useState<DependencyBindingType[]>([]);
  
  // System Credentials & Agent Credential Demands
  const [systemCredentials, setSystemCredentials] = useState<SystemCredentialItem[]>([]);
  const [credentialDemand, setCredentialDemand] = useState<SessionCredentialPrompt | null>(null);
  const [systemCredInputs, setSystemCredInputs] = useState<Record<string, string>>({});
  const [savingSystemCreds, setSavingSystemCreds] = useState(false);
  const [systemCredSaveSuccess, setSystemCredSaveSuccess] = useState(false);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [userInputs, setUserInputs] = useState<Record<string, string>>({});
  const [selectedExecutionMode, setSelectedExecutionMode] = useState<'faithful' | 'compatible' | 'simulation'>('faithful');

  // Model Connections & Multi-Model Gateway
  const [modelConnections, setModelConnections] = useState<ModelConnection[]>([]);
  const [testingConnId, setTestingConnId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, ModelConnectionTestResult>>({});
  const [agentModelSlots, setAgentModelSlots] = useState<any[]>([]);
  const [activeSlotBindings, setActiveSlotBindings] = useState<Record<string, string>>({});
  const abortControllers = React.useRef<Record<string, AbortController>>({});
  
  // Per-slot editable inline form states
  const [slotConfigs, setSlotConfigs] = useState<Record<string, SlotConfigState>>({});

  const handleCancelTesting = (slotId: string) => {
    if (abortControllers.current[slotId]) {
      abortControllers.current[slotId].abort();
      delete abortControllers.current[slotId];
    }
    setTestingConnId(null);
    setTestResults(prev => ({
      ...prev,
      [slotId]: {
        success: false,
        status: 'unhealthy',
        latency_ms: 0,
        message: 'Connection test cancelled by user.',
        supports_chat: false,
        supports_json: false,
      }
    }));
  };

  // Fetch agents list on mount
  useEffect(() => {
    fetchAgents().then(list => {
      setAgentsList(list);
      const targetId = agentIdFromUrl || selectedAgentId;
      if (targetId && list.some(a => a.id === targetId)) {
        setSelectedAgentId(targetId);
        const found = list.find(a => a.id === targetId);
        if (found) setCurrentAgent(found);
      } else if (list.length > 0) {
        setSelectedAgentId(list[0].id);
        setCurrentAgent(list[0]);
      }
    }).catch(console.error);
  }, [agentIdFromUrl]);

  // Reload dependency data & system credentials whenever selectedAgentId changes
  useEffect(() => {
    if (selectedAgentId) {
      const found = agentsList.find(a => a.id === selectedAgentId);
      if (found) setCurrentAgent(found);
      loadData(selectedAgentId);
    }
  }, [selectedAgentId, selectedExecutionMode]);

  const loadData = async (agentId: string) => {
    setLoading(true);
    try {
      const [deps, res, binds, sysCreds, credPrompt, conns, agentBindingsData] = await Promise.all([
        getAgentDependencies(agentId).catch(() => []),
        getPlatformResources().catch(() => []),
        getAgentBindings(agentId).catch(() => []),
        getSystemCredentials().catch(() => []),
        getAgentRequiredCredentials(agentId, selectedExecutionMode).catch(() => null),
        listModelConnections().catch(() => []),
        getAgentModelBindings(agentId).catch(() => null),
      ]);
      setDependencies(deps);
      setResources(res);
      setBindings(binds);
      setSystemCredentials(sysCreds);
      setCredentialDemand(credPrompt);
      setModelConnections(conns);
      
      if (agentBindingsData) {
        const slots = agentBindingsData.slots || [];
        setAgentModelSlots(slots);
        const currentBindings: Record<string, string> = {};
        const initialSlotConfigs: Record<string, SlotConfigState> = {};

        for (const slot of slots) {
          const boundId = slot.bound_connection_id || 'system_default';
          currentBindings[slot.slot_id] = boundId;

          const boundConn = conns.find((c: ModelConnection) => c.id === boundId);
          if (boundConn) {
            const isLocal = boundConn.is_local || boundConn.base_url?.includes('localhost') || boundConn.base_url?.includes('127.0.0.1');
            initialSlotConfigs[slot.slot_id] = {
              mode: isLocal ? 'local_model' : 'cloud_api',
              provider: boundConn.provider,
              base_url: boundConn.base_url,
              model_identifier: boundConn.model_identifier,
              api_key: boundConn.api_key || '',
            };
          } else {
            initialSlotConfigs[slot.slot_id] = {
              mode: 'system_default',
              provider: 'gemini',
              base_url: 'https://generativelanguage.googleapis.com/v1beta/openai',
              model_identifier: slot.detected_from_source || 'gemini-2.5-flash',
              api_key: '',
            };
          }
        }
        setActiveSlotBindings(currentBindings);
        setSlotConfigs(initialSlotConfigs);

        // Pre-populate testResults for already-saved slots so the button shows "Saved ✓ Re-test" on load
        const preloadedResults: Record<string, ModelConnectionTestResult> = {};
        for (const slot of slots) {
          const boundId = currentBindings[slot.slot_id];
          if (boundId && boundId !== 'system_default') {
            const boundConn = conns.find((c: ModelConnection) => c.id === boundId);
            if (boundConn) {
              preloadedResults[slot.slot_id] = {
                success: true,
                status: 'healthy',
                latency_ms: boundConn.latency_ms ?? 0,
                message: `Already saved: ${boundConn.model_identifier} @ ${boundConn.base_url}`,
                supports_chat: true,
                supports_json: false,
              };
            }
          }
        }
        if (Object.keys(preloadedResults).length > 0) {
          setTestResults(prev => ({ ...prev, ...preloadedResults }));
        }
      }
    } catch (e) {
      console.error('Failed to load setup gateway data:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSlotModeChange = async (slotId: string, newMode: 'system_default' | 'cloud_api' | 'local_model') => {
    const slot = agentModelSlots.find(s => s.slot_id === slotId);
    const prevConfig = slotConfigs[slotId] || {
      mode: 'system_default',
      provider: 'gemini',
      base_url: 'https://generativelanguage.googleapis.com/v1beta/openai',
      model_identifier: slot?.detected_from_source || 'gemini-2.5-flash',
      api_key: '',
    };

    let updatedConfig = { ...prevConfig, mode: newMode };

    if (newMode === 'system_default') {
      updatedConfig.provider = 'gemini';
      updatedConfig.base_url = 'https://generativelanguage.googleapis.com/v1beta/openai';
      updatedConfig.model_identifier = 'gemini-2.5-flash';
      updatedConfig.api_key = '';
      
      const updatedBindings = { ...activeSlotBindings, [slotId]: 'system_default' };
      setActiveSlotBindings(updatedBindings);
      if (selectedAgentId) {
        await updateAgentModelBindings(selectedAgentId, updatedBindings).catch(console.error);
      }
    } else if (newMode === 'cloud_api' && prevConfig.mode !== 'cloud_api') {
      updatedConfig.provider = 'gemini';
      updatedConfig.base_url = 'https://generativelanguage.googleapis.com/v1beta/openai';
      updatedConfig.model_identifier = 'gemini-2.5-flash';
    } else if (newMode === 'local_model' && prevConfig.mode !== 'local_model') {
      updatedConfig.provider = 'ollama';
      updatedConfig.base_url = 'http://localhost:11434/v1';
      updatedConfig.model_identifier = 'llama3.2';
      updatedConfig.api_key = '';
    }

    setSlotConfigs(prev => ({ ...prev, [slotId]: updatedConfig }));
  };

  const handleSaveSlotInlineConfig = async (slotId: string) => {
    const config = slotConfigs[slotId];
    if (!config) return;

    if (config.mode === 'system_default') {
      const updatedBindings = { ...activeSlotBindings, [slotId]: 'system_default' };
      setActiveSlotBindings(updatedBindings);
      if (selectedAgentId) {
        await updateAgentModelBindings(selectedAgentId, updatedBindings).catch(console.error);
      }
      return;
    }

    const DEFAULT_PRESET_URLS: Record<string, string> = {
      gemini: 'https://generativelanguage.googleapis.com/v1beta',
      openai: 'https://api.openai.com/v1',
      anthropic: 'https://api.anthropic.com/v1',
      openrouter: 'https://openrouter.ai/api/v1',
      groq: 'https://api.groq.com/openai/v1',
      deepseek: 'https://api.deepseek.com/v1',
      ollama: 'http://localhost:11434/v1',
      lm_studio: 'http://localhost:1234/v1',
      vllm: 'http://localhost:8000/v1',
    };

    const connName = `${slotId}_${config.mode === 'local_model' ? 'local' : 'cloud'}_${config.model_identifier}`;
    const targetUrl = config.base_url || DEFAULT_PRESET_URLS[config.provider] || 'https://generativelanguage.googleapis.com/v1beta';
    const isLocal = config.mode === 'local_model' || targetUrl.includes('localhost') || targetUrl.includes('127.0.0.1');

    const controller = new AbortController();
    abortControllers.current[slotId] = controller;

    try {
      setTestingConnId(slotId);
      const created = await createModelConnection({
        name: connName,
        provider: config.provider as any,
        base_url: targetUrl,
        model_identifier: config.model_identifier,
        api_key: config.api_key || null,
        role: 'test_agent_ai',
        is_local: isLocal,
      });

      setModelConnections(prev => [...prev.filter(c => c.name !== connName), created]);

      const updatedBindings = { ...activeSlotBindings, [slotId]: created.id };
      setActiveSlotBindings(updatedBindings);
      if (selectedAgentId) {
        await updateAgentModelBindings(selectedAgentId, updatedBindings);
      }

      const res = await testModelConnection({
        provider: created.provider,
        base_url: created.base_url,
        model_identifier: created.model_identifier,
        api_key: created.api_key || null,
      }, controller.signal).catch(err => ({
        success: false,
        status: 'unhealthy',
        latency_ms: 0,
        message: err.name === 'AbortError' ? 'Connection test cancelled by user.' : (err.message || 'Connection test failed'),
        supports_chat: false,
        supports_json: false,
      }));

      setTestResults(prev => ({ ...prev, [slotId]: res }));
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        alert(`Failed to save AI configuration for ${slotId}: ${err.message}`);
      }
    } finally {
      delete abortControllers.current[slotId];
      setTestingConnId(null);
    }
  };

  const handleSystemCredInput = (keyName: string, value: string) => {
    setSystemCredInputs(prev => ({ ...prev, [keyName]: value }));
  };

  const handleSaveSystemCredentials = async () => {
    if (Object.keys(systemCredInputs).length === 0) return;
    setSavingSystemCreds(true);
    try {
      const updated = await updateSystemCredentials(systemCredInputs);
      setSystemCredentials(updated);
      setSystemCredSaveSuccess(true);
      setTimeout(() => setSystemCredSaveSuccess(false), 3000);
      
      if (selectedAgentId) {
        const credPrompt = await getAgentRequiredCredentials(selectedAgentId, selectedExecutionMode);
        setCredentialDemand(credPrompt);
      }
    } catch (e) {
      console.error('Failed to save system credentials:', e);
    } finally {
      setSavingSystemCreds(false);
    }
  };

  const totalDeps = bindings.length;
  const resolvedDeps = bindings.filter(b => b.status === 'ready').length;
  const progressPct = totalDeps > 0 ? Math.round((resolvedDeps / totalDeps) * 100) : 100;

  // Check if any mandatory requirement is unfulfilled
  const mandatoryUnfulfilled = credentialDemand?.requirements?.some(r => !r.is_optional && !r.is_fulfilled) || false;

  if (loading && !currentAgent) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-4 font-mono">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-cyan-500 via-indigo-500 to-violet-500 p-0.5 mx-auto animate-pulse">
            <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
              <Shield className="w-7 h-7 text-cyan-400 animate-spin" />
            </div>
          </div>
          <p className="text-sm text-slate-400">Performing deep static analysis of agent code & requirements...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 font-mono">
      
      {/* 🛑 Execution Blocked Banner */}
      {isBlockedRedirect && (
        <div className="p-4 rounded-2xl glass-panel border border-rose-500/50 bg-rose-950/30 flex items-start space-x-3.5 shadow-xl animate-fadeIn">
          <div className="p-2.5 rounded-xl bg-rose-500/20 shrink-0">
            <XCircle className="w-6 h-6 text-rose-400" />
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-extrabold text-rose-200">Execution Blocked by Setup Gateway</h3>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                ACTION REQUIRED
              </span>
            </div>
            <p className="text-xs text-slate-300 mt-1">
              Required credentials or API keys were missing for agent <strong className="text-white">{currentAgent?.display_name || currentAgent?.name}</strong>.
              {missingFromUrl && <span> Missing requirements: <code className="text-rose-300 bg-slate-900 px-1.5 py-0.5 rounded">{missingFromUrl}</code></span>}
            </p>
          </div>
        </div>
      )}

      {/* Header & Agent Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-tr from-purple-500 via-indigo-500 to-cyan-500 p-0.5">
            <div className="w-9 h-9 bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Shield className="w-5 h-5 text-cyan-400" />
            </div>
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100">Setup Control Center</h1>
            <p className="text-xs text-slate-400 mt-0.5">
              {currentAgent ? `${currentAgent.display_name || currentAgent.name} · ${currentAgent.id}` : 'Select an agent'}
            </p>
          </div>
        </div>

        {/* Agent Dropdown */}
        <div className="flex items-center space-x-2">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider hidden sm:inline">Target Agent:</label>
          <select
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-lg px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none"
          >
            {agentsList.map(a => (
              <option key={a.id} value={a.id}>
                {a.display_name || a.name} ({a.id})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ── AGENT DEEP ANALYSIS SUMMARY BANNER ── */}
      {currentAgent && (
        <div className="p-5 rounded-2xl border border-cyan-500/30 bg-slate-950/90 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
            <div className="flex items-center space-x-2 text-cyan-300">
              <FileCode className="w-4 h-4 text-cyan-400" />
              <h2 className="text-xs font-bold uppercase tracking-wider">AGENT CODE ANALYSIS & GOAL SUMMARY</h2>
            </div>
            <span className="px-2 py-0.5 text-[9px] font-bold rounded bg-cyan-950 text-cyan-300 border border-cyan-500/30">
              DOMAIN: {currentAgent.domain?.toUpperCase() || 'GENERAL'}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="space-y-1">
              <span className="text-[10px] text-slate-400 uppercase font-bold">Agent Description & Aim:</span>
              <p className="text-slate-200 leading-relaxed font-sans">{currentAgent.description || 'Custom autonomous agent pipeline.'}</p>
            </div>
            <div className="space-y-1">
              <span className="text-[10px] text-slate-400 uppercase font-bold">Detected Architecture:</span>
              <div className="text-slate-300 space-y-0.5">
                <div>AI Model Roles: <b className="text-purple-300">{agentModelSlots.length} detected</b></div>
                <div>Tool Functions: <b className="text-cyan-300">{currentAgent.tools?.length || 0} discovered</b></div>
                <div>External Secrets: <b className="text-indigo-300">{credentialDemand?.requirements?.length || 0} scanned</b></div>
              </div>
            </div>
            <div className="space-y-1">
              <span className="text-[10px] text-slate-400 uppercase font-bold">System Prompt Blueprint:</span>
              <p className="text-slate-400 truncate max-w-full font-mono bg-slate-900 p-1.5 rounded border border-slate-800 text-[10px]" title={currentAgent.system_prompt}>
                {currentAgent.system_prompt || 'Standard goal-seeking system instruction.'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── SECTION 1: AI MODEL & LLM REQUIREMENTS (EVERY POSITION EXPLAINED) ── */}
      <div className="p-6 rounded-2xl border border-purple-500/40 bg-slate-950/80 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3 border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <Cpu className="w-6 h-6 text-purple-400" />
            <div>
              <h2 className="text-base font-extrabold text-white">1. AI MODEL & LLM REQUIREMENTS ({agentModelSlots.length})</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Code variables and environment keys for each AI instantiation slot detected in source code.
              </p>
            </div>
          </div>
        </div>

        {/* AI Role Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {agentModelSlots.map(slot => {
            const config = slotConfigs[slot.slot_id] || {
              mode: 'system_default',
              provider: 'gemini',
              base_url: 'https://generativelanguage.googleapis.com/v1beta/openai',
              model_identifier: slot.detected_from_source || 'gemini-2.5-flash',
              api_key: '',
            };

            const testResult = testResults[slot.slot_id];
            const isSavingOrTesting = testingConnId === slot.slot_id;

            const codeVar = slot.code_variable || slot.slot_id;
            const envVar = slot.env_var || (slot.slot_id === 'critic_llm' ? 'PLATFORM_SAFETY_LLM' : 'OPENAI_API_KEY');

            return (
              <div key={slot.slot_id} className="p-5 rounded-2xl border border-slate-800 bg-slate-900/80 space-y-4 shadow-xl">
                {/* Header with Variable Name & Env Var info */}
                <div className="space-y-1.5 border-b border-slate-800 pb-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-cyan-300 flex items-center gap-1.5">
                      <Code className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Variable in Code: <code className="text-white bg-slate-950 px-1.5 py-0.5 rounded">{codeVar}</code></span>
                    </span>
                    <div className="flex items-center space-x-1.5">
                      {activeSlotBindings[slot.slot_id] && activeSlotBindings[slot.slot_id] !== 'system_default' && (
                        <span className="px-2 py-0.5 text-[9px] font-bold rounded bg-emerald-950/80 text-emerald-300 border border-emerald-500/50 flex items-center space-x-1 shadow">
                          <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" />
                          <span>Saved & Active</span>
                        </span>
                      )}
                      <span className={`px-2 py-0.5 text-[9px] font-bold rounded ${
                        config.mode === 'system_default'
                          ? 'bg-amber-950/60 text-amber-400 border border-amber-500/30'
                          : config.mode === 'local_model'
                          ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/30'
                          : 'bg-purple-950/60 text-purple-300 border border-purple-500/30'
                      }`}>
                        {config.mode === 'system_default'
                          ? '✦ Default AI'
                          : config.mode === 'local_model'
                          ? '🖥 Local ML'
                          : '☁ Cloud API'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-slate-400">
                    <span>Populates Env: <code className="text-indigo-300 font-bold bg-slate-950 px-1 rounded">{envVar}</code></span>
                    <span>Default Model: <b className="text-emerald-400">{slot.detected_from_source || 'gemini-2.5-flash'}</b></span>
                  </div>

                  {slot.explanation && (
                    <p className="text-[10px] text-slate-400 bg-slate-950/60 p-2 rounded border border-slate-800/80 leading-tight">
                      <Info className="w-3 h-3 text-purple-400 inline mr-1" />
                      {slot.explanation}
                    </p>
                  )}
                </div>

                {/* 3 Source Options Toggle */}
                <div className="space-y-1.5">
                  <label className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">
                    Choose AI Source for {codeVar}:
                  </label>
                  <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-slate-950 border border-slate-800 text-[10px]">
                    <button
                      onClick={() => handleSlotModeChange(slot.slot_id, 'system_default')}
                      className={`py-1.5 px-1 rounded-lg font-bold transition text-center cursor-pointer ${
                        config.mode === 'system_default'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow'
                          : 'text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      Default
                    </button>
                    <button
                      onClick={() => handleSlotModeChange(slot.slot_id, 'cloud_api')}
                      className={`py-1.5 px-1 rounded-lg font-bold transition text-center cursor-pointer ${
                        config.mode === 'cloud_api'
                          ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow'
                          : 'text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      Cloud API
                    </button>
                    <button
                      onClick={() => handleSlotModeChange(slot.slot_id, 'local_model')}
                      className={`py-1.5 px-1 rounded-lg font-bold transition text-center cursor-pointer ${
                        config.mode === 'local_model'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow'
                          : 'text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      Local ML
                    </button>
                  </div>
                </div>

                {/* ── MODE 1: DEFAULT SETUP (PLATFORM PRE-FILLED) ── */}
                {config.mode === 'system_default' && (
                  <div className="p-3 rounded-xl bg-slate-950/80 border border-amber-500/20 space-y-1.5 text-[11px]">
                    <div className="flex justify-between items-center text-slate-300">
                      <span className="text-slate-500">Platform Pre-filled Model:</span>
                      <span className="text-amber-300 font-bold">Gemini 2.5 Flash</span>
                    </div>
                    <div className="flex justify-between items-center text-slate-300">
                      <span className="text-slate-500">Endpoint & Auth:</span>
                      <span className="text-emerald-400 font-bold">Platform Free Mock (Ready)</span>
                    </div>
                    <p className="text-[9px] text-slate-500 pt-1 border-t border-slate-900">
                      Pre-filled website default setup. Click "Cloud API" or "Local ML" above to edit directly in-place.
                    </p>
                  </div>
                )}

                {/* ── MODE 2: USER CLOUD AI API (INLINE EDITABLE FIELDS) ── */}
                {config.mode === 'cloud_api' && (
                  <div className="space-y-3 pt-1 border-t border-slate-800/80 text-xs">
                    <div>
                      <label className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold mb-1">
                        Select Provider Preset:
                      </label>
                      <div className="flex flex-wrap gap-1">
                        {[
                          { id: 'gemini',      label: 'Gemini',      url: 'https://generativelanguage.googleapis.com/v1beta',        model: 'gemini-2.5-flash' },
                          { id: 'openai',      label: 'OpenAI',      url: 'https://api.openai.com/v1',                              model: 'gpt-4o-mini' },
                          { id: 'anthropic',   label: 'Anthropic',   url: 'https://api.anthropic.com/v1',                           model: 'claude-3-5-sonnet-20241022' },
                          { id: 'openrouter',  label: 'OpenRouter',  url: 'https://openrouter.ai/api/v1',                           model: 'openai/gpt-4o-mini' },
                          { id: 'groq',        label: 'Groq',        url: 'https://api.groq.com/openai/v1',                         model: 'llama-3.3-70b-versatile' },
                          { id: 'deepseek',    label: 'DeepSeek',    url: 'https://api.deepseek.com/v1',                            model: 'deepseek-chat' },
                        ].map(p => (
                          <button
                            key={p.id}
                            onClick={() => setSlotConfigs(prev => ({
                              ...prev,
                              [slot.slot_id]: {
                                ...config,
                                provider: p.id,
                                base_url: p.url,
                                model_identifier: p.model,
                              }
                            }))}
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border transition cursor-pointer ${
                              config.provider === p.id
                                ? 'bg-purple-900/60 border-purple-400 text-purple-200'
                                : 'border-slate-800 bg-slate-950 text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            {p.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="text-[10px] text-slate-300 font-bold block mb-1">
                        Select Model for {config.provider.toUpperCase()}:
                      </label>
                      <div className="flex flex-wrap gap-1 mb-2">
                        {(CURATED_MODELS_PER_PROVIDER[config.provider] || []).map(m => (
                          <button
                            key={m.id}
                            type="button"
                            onClick={() => setSlotConfigs(prev => ({
                              ...prev,
                              [slot.slot_id]: { ...config, model_identifier: m.id }
                            }))}
                            className={`px-2 py-1 rounded text-[10px] font-mono border transition flex items-center space-x-1 cursor-pointer ${
                              config.model_identifier === m.id
                                ? 'bg-purple-950 border-purple-400 text-purple-200 font-bold shadow'
                                : 'border-slate-800 bg-slate-950/70 text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            <span>{m.label}</span>
                            {m.badge && (
                              <span className="text-[8px] px-1 py-0.2 rounded bg-purple-900/60 text-purple-300 ml-1">
                                {m.badge}
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                      <input
                        type="text"
                        placeholder="Or enter custom model name..."
                        value={config.model_identifier}
                        onChange={e => setSlotConfigs(prev => ({
                          ...prev,
                          [slot.slot_id]: { ...config, model_identifier: e.target.value }
                        }))}
                        className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-emerald-300 font-mono text-xs focus:border-purple-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="text-[10px] text-slate-300 font-bold block mb-1">API Key <span className="text-rose-400">*</span></label>
                      <input
                        type="password"
                        placeholder="Paste your API key here..."
                        value={config.api_key}
                        onChange={e => setSlotConfigs(prev => ({
                          ...prev,
                          [slot.slot_id]: { ...config, api_key: e.target.value }
                        }))}
                        className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-white font-mono text-xs focus:border-purple-500 focus:outline-none"
                      />
                    </div>

                    <div className="flex items-center justify-between pt-1 flex-wrap gap-2">
                      {testResult && (
                        <span className={`text-[10px] font-medium ${testResult.success ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {testResult.success ? `✓ Ping: ${testResult.latency_ms}ms (Saved to Vault & Bound to ${codeVar})` : `⚠️ ${testResult.message}`}
                        </span>
                      )}
                      <div className="ml-auto flex items-center space-x-2">
                        {isSavingOrTesting && (
                          <button
                            type="button"
                            onClick={() => handleCancelTesting(slot.slot_id)}
                            className="px-2.5 py-1.5 rounded-lg bg-rose-950 hover:bg-rose-900 border border-rose-500/40 text-rose-300 text-[10px] font-bold transition flex items-center space-x-1 cursor-pointer"
                          >
                            <XCircle className="w-3 h-3 text-rose-400" />
                            <span>Cancel Test</span>
                          </button>
                        )}
                        <button
                          disabled={isSavingOrTesting || !config.model_identifier.trim() || !config.api_key.trim()}
                          onClick={() => handleSaveSlotInlineConfig(slot.slot_id)}
                          className={`px-3 py-1.5 rounded-lg disabled:opacity-40 text-white text-[11px] font-bold shadow transition flex items-center space-x-1 cursor-pointer ${
                            testResult?.success && activeSlotBindings[slot.slot_id] && activeSlotBindings[slot.slot_id] !== 'system_default'
                              ? 'bg-emerald-700/60 hover:bg-emerald-600/80 border border-emerald-500/50'
                              : 'bg-purple-600 hover:bg-purple-500'
                          }`}
                        >
                          {isSavingOrTesting ? (
                            <><RefreshCw className="w-3 h-3 animate-spin" /><span>Testing...</span></>
                          ) : testResult?.success && activeSlotBindings[slot.slot_id] && activeSlotBindings[slot.slot_id] !== 'system_default' ? (
                            <><CheckCircle className="w-3 h-3 text-emerald-300" /><span>Saved ✓ &nbsp;Re-test</span></>
                          ) : (
                            <><Check className="w-3 h-3" /><span>Save & Test AI Key</span></>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* ── MODE 3: USER LOCAL ML / LLM MODEL (INLINE EDITABLE FIELDS) ── */}
                {config.mode === 'local_model' && (
                  <div className="space-y-3 pt-1 border-t border-slate-800/80 text-xs">
                    <div>
                      <label className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold mb-1">
                        Select Server Software:
                      </label>
                      <div className="grid grid-cols-3 gap-1">
                        {[
                          { id: 'ollama',    label: 'Ollama',    port: '11434', model: 'llama3.2' },
                          { id: 'lm_studio', label: 'LM Studio', port: '1234',  model: 'qwen2.5-coder-7b' },
                          { id: 'vllm',      label: 'vLLM',      port: '8000',  model: 'Llama-3.1-8B' },
                        ].map(s => (
                          <button
                            key={s.id}
                            onClick={() => setSlotConfigs(prev => ({
                              ...prev,
                              [slot.slot_id]: {
                                ...config,
                                provider: s.id,
                                base_url: `http://localhost:${s.port}/v1`,
                                model_identifier: s.model,
                              }
                            }))}
                            className={`py-1 px-1 rounded text-[10px] font-bold border transition cursor-pointer text-center ${
                              config.provider === s.id
                                ? 'bg-emerald-900/60 border-emerald-400 text-emerald-200'
                                : 'border-slate-800 bg-slate-950 text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            {s.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="text-[10px] text-slate-300 font-bold block mb-1">Server Address <span className="text-rose-400">*</span></label>
                      <input
                        type="text"
                        placeholder="http://localhost:11434/v1"
                        value={config.base_url}
                        onChange={e => setSlotConfigs(prev => ({
                          ...prev,
                          [slot.slot_id]: { ...config, base_url: e.target.value }
                        }))}
                        className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-cyan-300 font-mono text-xs focus:border-emerald-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="text-[10px] text-slate-300 font-bold block mb-1">Model Name <span className="text-rose-400">*</span></label>
                      <input
                        type="text"
                        placeholder="e.g. llama3.2, qwen2.5:7b, mistral"
                        value={config.model_identifier}
                        onChange={e => setSlotConfigs(prev => ({
                          ...prev,
                          [slot.slot_id]: { ...config, model_identifier: e.target.value }
                        }))}
                        className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-emerald-300 font-mono text-xs focus:border-emerald-500 focus:outline-none"
                      />
                    </div>

                    <div className="flex items-center justify-between pt-1 flex-wrap gap-2">
                      {testResult && (
                        <span className={`text-[10px] font-medium ${testResult.success ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {testResult.success ? `✓ Ping: ${testResult.latency_ms}ms (Saved to Vault & Bound to ${codeVar})` : `⚠️ ${testResult.message}`}
                        </span>
                      )}
                      <div className="ml-auto flex items-center space-x-2">
                        {isSavingOrTesting && (
                          <button
                            type="button"
                            onClick={() => handleCancelTesting(slot.slot_id)}
                            className="px-2.5 py-1.5 rounded-lg bg-rose-950 hover:bg-rose-900 border border-rose-500/40 text-rose-300 text-[10px] font-bold transition flex items-center space-x-1 cursor-pointer"
                          >
                            <XCircle className="w-3 h-3 text-rose-400" />
                            <span>Cancel Test</span>
                          </button>
                        )}
                        <button
                          disabled={isSavingOrTesting || !config.base_url.trim() || !config.model_identifier.trim()}
                          onClick={() => handleSaveSlotInlineConfig(slot.slot_id)}
                          className={`px-3 py-1.5 rounded-lg disabled:opacity-40 text-white text-[11px] font-bold shadow transition flex items-center space-x-1 cursor-pointer ${
                            testResult?.success && activeSlotBindings[slot.slot_id] && activeSlotBindings[slot.slot_id] !== 'system_default'
                              ? 'bg-emerald-700/60 hover:bg-emerald-600/80 border border-emerald-500/50'
                              : 'bg-emerald-600 hover:bg-emerald-500'
                          }`}
                        >
                          {isSavingOrTesting ? (
                            <><RefreshCw className="w-3 h-3 animate-spin" /><span>Testing...</span></>
                          ) : testResult?.success && activeSlotBindings[slot.slot_id] && activeSlotBindings[slot.slot_id] !== 'system_default' ? (
                            <><CheckCircle className="w-3 h-3 text-emerald-300" /><span>Saved ✓ &nbsp;Re-test</span></>
                          ) : (
                            <><Check className="w-3 h-3" /><span>Save & Test Local Model</span></>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* DETECTED TOOL FUNCTIONS WITH "WHY USED" RATIONALE */}
        {currentAgent?.tools && currentAgent.tools.length > 0 && (
          <div className="pt-4 border-t border-slate-800/80 space-y-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Server className="w-4 h-4 text-cyan-400" />
              <span>DETECTED TOOL FUNCTIONS & WHY THEY ARE USED IN CODE ({currentAgent.tools.length})</span>
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {currentAgent.tools.map(tool => (
                <div key={tool.name} className="p-3.5 rounded-xl border border-slate-800 bg-slate-900/60 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-100">{tool.name}()</span>
                    <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold ${
                      tool.risk === 'high' ? 'bg-rose-950 text-rose-300 border border-rose-500/20' : 'bg-slate-800 text-slate-400'
                    }`}>
                      {tool.risk.toUpperCase()} RISK
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-tight">{tool.description}</p>
                  
                  {/* Explicit "WHY USED IN AGENT CODE" Rationale */}
                  <div className="pt-1.5 border-t border-slate-800/60 text-[10px] text-cyan-300/90 flex items-start space-x-1">
                    <Info className="w-3 h-3 text-cyan-400 shrink-0 mt-0.5" />
                    <span>
                      <b>WHY USED:</b> Called by agent during execution to perform {tool.canonical_capability || tool.name} capability.
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── SECTION 2: OTHER REQUIREMENTS (SERVICES, APIS & ENVIRONMENT SECRETS) ── */}
      <div className="p-6 rounded-2xl border border-indigo-500/30 bg-slate-950/80 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-2 border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <Key className="w-6 h-6 text-indigo-400" />
            <div>
              <h2 className="text-base font-extrabold text-white">2. OTHER REQUIREMENTS (SERVICES, APIS & ENVIRONMENT SECRETS)</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                All non-AI third-party requirements detected in code. Explains code variable and environment key for each requirement.
              </p>
            </div>
          </div>
        </div>

        {(() => {
          const nonAiReqs = (credentialDemand?.requirements || []).filter(r => 
            !['OPENAI_API_KEY', 'GEMINI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPSEEK_API_KEY', 'GROQ_API_KEY', 'OPENROUTER_API_KEY', 'PLATFORM_SAFETY_LLM'].includes(r.key_name.toUpperCase())
          );
          return nonAiReqs.length > 0 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                {nonAiReqs.map(req => {
                const isNoDefault = !req.is_optional && !req.is_fulfilled && !systemCredInputs[req.key_name];
                return (
                  <div
                    key={req.key_name}
                    className={`p-4 rounded-xl border space-y-2.5 transition-all ${
                      req.is_fulfilled
                        ? 'border-emerald-500/40 bg-emerald-950/15'
                        : isNoDefault
                        ? 'border-rose-500/50 bg-rose-950/20'
                        : 'border-amber-500/40 bg-amber-950/15'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-100 flex items-center gap-1">
                        <Key className="w-3.5 h-3.5 text-indigo-400" />
                        <span>Env Var: <code className="text-cyan-300">{req.key_name}</code></span>
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${
                        req.is_fulfilled
                          ? 'bg-emerald-950 text-emerald-300 border-emerald-500/30'
                          : isNoDefault
                          ? 'bg-rose-950 text-rose-300 border border-rose-500/40'
                          : 'bg-amber-950 text-amber-300 border-amber-500/30'
                      }`}>
                        {req.is_fulfilled ? '✓ PLATFORM DEFAULT' : isNoDefault ? '⚠️ REQUIRED (NO DEFAULT)' : 'CUSTOM OVERRIDE'}
                      </span>
                    </div>

                    <p className="text-[11px] text-slate-400 leading-tight">{req.description}</p>
                    
                    <div className="text-[10px] text-slate-400 bg-slate-950 p-2 rounded border border-slate-800">
                      <b>Code Reference:</b> Read via <code>os.getenv("{req.key_name}")</code> in agent source.
                    </div>

                    <div className="relative mt-2">
                      <Lock className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500" />
                      <input
                        type="password"
                        placeholder={isNoDefault ? `Enter required ${req.key_name}...` : `Enter custom ${req.key_name}...`}
                        value={systemCredInputs[req.key_name] || ''}
                        onChange={e => handleSystemCredInput(req.key_name, e.target.value)}
                        className={`w-full pl-7 pr-3 py-1.5 rounded-lg bg-slate-950 border text-xs font-mono text-emerald-400 focus:ring-1 focus:outline-none ${
                          isNoDefault ? 'border-rose-500 focus:ring-rose-500' : 'border-slate-700 focus:ring-indigo-500'
                        }`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <p className="text-xs text-slate-400">
                Values are saved directly into your agent's runtime vault. Missing keys without defaults block test execution.
              </p>
              <div className="flex items-center space-x-3">
                {systemCredSaveSuccess && (
                  <span className="text-xs text-emerald-400 flex items-center space-x-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Saved!</span>
                  </span>
                )}
                <button
                  onClick={handleSaveSystemCredentials}
                  disabled={savingSystemCreds || Object.keys(systemCredInputs).length === 0}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-bold text-xs shadow-lg shadow-indigo-500/20 flex items-center space-x-1.5 transition disabled:opacity-40 cursor-pointer"
                >
                  {savingSystemCreds ? (
                    <><RefreshCw className="w-3.5 h-3.5 animate-spin" /><span>Saving...</span></>
                  ) : (
                    <><Key className="w-3.5 h-3.5" /><span>Save Secrets</span></>
                  )}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-6 text-center rounded-xl border border-emerald-500/30 bg-emerald-950/10 space-y-2">
            <CheckCircle2 className="w-6 h-6 text-emerald-400 mx-auto" />
            <h3 className="text-xs font-bold text-emerald-300 uppercase tracking-wide">
              No External Non-AI API Secrets Required
            </h3>
            <p className="text-xs text-slate-400">
              Agent <strong className="text-cyan-300">{currentAgent?.display_name || currentAgent?.name}</strong> does not require third-party non-AI API keys. Platform defaults are active.
            </p>
          </div>
        );
      })()}
      </div>

      {/* ── SECTION 3: SANDBOX ENVIRONMENT & EXECUTION MODE ──────────────── */}
      <div className="p-6 rounded-2xl border border-cyan-500/30 bg-slate-950/80 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-2 border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <Shield className="w-6 h-6 text-cyan-400" />
            <div>
              <h2 className="text-base font-extrabold text-white">3. SANDBOX ENVIRONMENT & EXECUTION MODE</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Select execution fidelity mode and inspect platform sandbox health.
              </p>
            </div>
          </div>
        </div>

        {/* Execution Mode Selector */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            onClick={() => setSelectedExecutionMode('faithful')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              selectedExecutionMode === 'faithful'
                ? 'border-emerald-500 bg-emerald-950/20 ring-1 ring-emerald-500'
                : 'border-slate-800 bg-slate-900/40 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-emerald-400 uppercase">MODE 1 — FAITHFUL</span>
              <span className="px-2 py-0.5 rounded text-[9px] bg-emerald-500/20 text-emerald-300">HIGH FIDELITY</span>
            </div>
            <p className="text-xs font-semibold text-slate-200">Original Model Execution</p>
            <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
              Executes agent using bound model connections & exact code paths.
            </p>
          </div>

          <div
            onClick={() => setSelectedExecutionMode('compatible')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              selectedExecutionMode === 'compatible'
                ? 'border-amber-500 bg-amber-950/20 ring-1 ring-amber-500'
                : 'border-slate-800 bg-slate-900/40 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-amber-400 uppercase">MODE 2 — COMPATIBLE</span>
              <span className="px-2 py-0.5 rounded text-[9px] bg-amber-500/20 text-amber-300">MEDIUM FIDELITY</span>
            </div>
            <p className="text-xs font-semibold text-slate-200">Alternative Model Substitute</p>
            <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
              Substitutes platform models (e.g. Gemini Flash) when missing credentials.
            </p>
          </div>

          <div
            onClick={() => setSelectedExecutionMode('simulation')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              selectedExecutionMode === 'simulation'
                ? 'border-indigo-500 bg-indigo-950/20 ring-1 ring-indigo-500'
                : 'border-slate-800 bg-slate-900/40 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-indigo-400 uppercase">MODE 3 — SIMULATION</span>
              <span className="px-2 py-0.5 rounded text-[9px] bg-indigo-500/20 text-indigo-300">ZERO COST MOCK</span>
            </div>
            <p className="text-xs font-semibold text-slate-200">Deterministic MockLLM</p>
            <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
              Uses MockLLM for zero-cost deterministic sandbox testing.
            </p>
          </div>
        </div>

        {/* Dependency Resolution Progress */}
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400 uppercase">Sandbox Environment Resolution</span>
            <span className="text-slate-300">
              <span className="text-cyan-400 font-bold">{resolvedDeps}</span>/{totalDeps} resolved
            </span>
          </div>
          <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500 transition-all duration-700 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Footer Action Bar */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate("/agents")}
            className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition"
          >
            ← Back to Agents
          </button>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate(`/scenarios?agentId=${selectedAgentId}`)}
            className="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs flex items-center space-x-2 transition"
          >
            <Layers className="w-4 h-4 text-cyan-400" />
            <span>Scenario Library</span>
          </button>

          <button
            disabled={mandatoryUnfulfilled}
            onClick={() => navigate(`/executions?agentId=${selectedAgentId}`)}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-600 hover:from-emerald-400 hover:to-cyan-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-extrabold text-xs shadow-lg shadow-emerald-500/25 flex items-center space-x-2 transition-all hover:scale-[1.02] active:scale-95 cursor-pointer"
          >
            <Play className="w-4 h-4 fill-white" />
            <span>Proceed to Run Execution</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Live Process Monitor */}
      <LiveProcessMonitor />
    </div>
  );
};
