import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Server,
  Zap,
  CheckCircle2,
  AlertCircle,
  Clock,
  Trash2,
  Plus,
  RefreshCw,
  HelpCircle,
  Activity,
  Terminal,
  Layers,
  ShieldCheck,
} from 'lucide-react';
import {
  listModelConnections,
  createModelConnection,
  testModelConnection,
  deleteModelConnection,
  setActiveModelConnection,
} from '../api/client';
import type { ModelConnection, ModelConnectionTestResult } from '../api/client';

export const ModelConnectionsPage: React.FC = () => {
  const [connections, setConnections] = useState<ModelConnection[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [testing, setTesting] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<ModelConnectionTestResult | null>(null);

  // Form State
  const [name, setName] = useState<string>('Google Gemini Flash');
  const [provider, setProvider] = useState<string>('gemini');
  const [baseUrl, setBaseUrl] = useState<string>('https://generativelanguage.googleapis.com/v1beta');
  const [modelIdentifier, setModelIdentifier] = useState<string>('gemini-3.7-flash');
  const [apiKey, setApiKey] = useState<string>('');
  const [role, setRole] = useState<string>('test_agent_ai');
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadConnections = async () => {
    setLoading(true);
    try {
      const data = await listModelConnections();
      setConnections(data);
    } catch (err: any) {
      console.error('Error fetching model connections:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConnections();
  }, []);

  const handleProviderPreset = (selectedProvider: string) => {
    setProvider(selectedProvider);
    if (selectedProvider === 'gemini') {
      setName('Google Gemini Flash');
      setBaseUrl('https://generativelanguage.googleapis.com/v1beta');
      setModelIdentifier('gemini-3.7-flash');
    } else if (selectedProvider === 'openrouter') {
      setName('OpenRouter Unified Gateway');
      setBaseUrl('https://openrouter.ai/api/v1');
      setModelIdentifier('anthropic/claude-3.5-sonnet');
    } else if (selectedProvider === 'openai') {
      setName('OpenAI GPT-4o');
      setBaseUrl('https://api.openai.com/v1');
      setModelIdentifier('gpt-4o');
    } else if (selectedProvider === 'anthropic') {
      setName('Anthropic Claude');
      setBaseUrl('https://api.anthropic.com/v1');
      setModelIdentifier('claude-3-5-sonnet-20241022');
    } else if (selectedProvider === 'groq') {
      setName('Groq Fast Llama');
      setBaseUrl('https://api.groq.com/openai/v1');
      setModelIdentifier('llama-3.3-70b-versatile');
    } else if (selectedProvider === 'deepseek') {
      setName('DeepSeek Reasoner');
      setBaseUrl('https://api.deepseek.com/v1');
      setModelIdentifier('deepseek-chat');
    } else if (selectedProvider === 'ollama') {
      setName('Local Ollama Qwen');
      setBaseUrl('http://localhost:11434/v1');
      setModelIdentifier('qwen2.5-coder:7b');
    } else if (selectedProvider === 'vllm') {
      setName('Local vLLM Server');
      setBaseUrl('http://localhost:8000/v1');
      setModelIdentifier('meta-llama/Llama-3.1-8B-Instruct');
    } else if (selectedProvider === 'lm_studio') {
      setName('LM Studio Local');
      setBaseUrl('http://localhost:1234/v1');
      setModelIdentifier('qwen2.5-coder-7b-instruct');
    } else if (selectedProvider === 'openai_compatible') {
      setName('Custom OpenAI-Compatible API');
      setBaseUrl('https://your-endpoint.com/v1');
      setModelIdentifier('custom-model-id');
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      const result = await testModelConnection({
        provider,
        base_url: baseUrl,
        model_identifier: modelIdentifier,
        api_key: apiKey || null,
      });
      setTestResult(result);
    } catch (err: any) {
      setError(err.message || 'Connection test failed');
    } finally {
      setTesting(false);
    }
  };

  const handleSaveConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    try {
      await createModelConnection({
        name,
        provider: provider as any,
        base_url: baseUrl,
        model_identifier: modelIdentifier,
        api_key: apiKey || null,
        role: role as any,
        is_local: baseUrl.includes('localhost') || baseUrl.includes('127.0.0.1'),
      });
      setSuccessMsg(`Successfully registered model connection '${name}'`);
      loadConnections();
    } catch (err: any) {
      setError(err.message || 'Failed to save model connection');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteModelConnection(id);
      loadConnections();
    } catch (err: any) {
      console.error('Error deleting connection:', err);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-indigo-500/20 to-cyan-500/20 border border-indigo-500/30 text-cyan-400">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-2xl font-extrabold tracking-tight text-white font-mono">
                  MODEL CONNECTIONS & LOCAL LLMS
                </h1>
                <span className="px-2 py-0.5 text-xs font-mono rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                  OLLAMA / VLLM / OPENAI-COMPATIBLE
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-0.5">
                Connect your locally running models or self-hosted endpoints to benchmark performance and generate training data.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={loadConnections}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-mono flex items-center space-x-1.5"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Endpoints</span>
        </button>
      </div>

      {/* Honest Boundary Banner */}
      <div className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-950/20 text-xs text-indigo-200 flex items-start space-x-3">
        <ShieldCheck className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-white">Truthful Model Improvement Architecture</p>
          <p className="mt-0.5 text-indigo-300/90 leading-relaxed">
            ForgeX tests your agents against real model endpoints. If you connect a local or self-hosted model (Ollama/vLLM/LM Studio), you can benchmark it and export fine-tuning datasets. Note: ForgeX does <strong>not</strong> claim to train proprietary closed APIs (OpenAI/Gemini).
          </p>
        </div>
      </div>

      {/* Main Grid: Add Connection Form (Left) & Active Connections (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Form */}
        <div className="lg:col-span-5 space-y-6">
          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur-xl">
            <h2 className="text-sm font-bold font-mono text-white flex items-center space-x-2 border-b border-slate-800 pb-3">
              <Plus className="w-4 h-4 text-cyan-400" />
              <span>REGISTER NEW MODEL ENDPOINT</span>
            </h2>

            <form onSubmit={handleSaveConnection} className="space-y-4 mt-4">
              {/* Provider Quick Presets */}
              <div>
                <label className="block text-xs font-mono text-slate-300 font-bold mb-1.5">Select Model Provider</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                  {[
                    { id: 'gemini', label: 'Google Gemini' },
                    { id: 'openrouter', label: 'OpenRouter' },
                    { id: 'openai', label: 'OpenAI' },
                    { id: 'anthropic', label: 'Anthropic' },
                    { id: 'groq', label: 'Groq LPU' },
                    { id: 'deepseek', label: 'DeepSeek' },
                    { id: 'ollama', label: 'Ollama Local' },
                    { id: 'vllm', label: 'vLLM Server' },
                    { id: 'lm_studio', label: 'LM Studio' },
                    { id: 'openai_compatible', label: 'Custom API' },
                  ].map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handleProviderPreset(p.id)}
                      className={`px-2.5 py-1.5 rounded-lg text-xs font-mono transition border text-center cursor-pointer ${
                        provider === p.id
                          ? 'bg-cyan-950 text-cyan-200 border-cyan-500 font-bold shadow-sm'
                          : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Name */}
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Display Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-cyan-500"
                />
              </div>

              {/* Base URL */}
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Base URL Endpoint</label>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  required
                  placeholder="https://generativelanguage.googleapis.com/v1beta/openai"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-cyan-500"
                />
              </div>

              {/* Model Identifier */}
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Model Identifier / Tag</label>
                <input
                  type="text"
                  value={modelIdentifier}
                  onChange={(e) => setModelIdentifier(e.target.value)}
                  required
                  placeholder="e.g. gemini-3.7-flash or gpt-4o"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-cyan-300 font-bold focus:outline-none focus:border-cyan-500"
                />
              </div>

              {/* API Key */}
              <div>
                <label className="block text-xs font-mono text-slate-300 font-bold mb-1">
                  API Key {['ollama', 'vllm', 'lm_studio'].includes(provider) ? '(Optional for local)' : '(Required for cloud API)'}
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={
                    provider === 'gemini' ? 'AIzaSy...' :
                    provider === 'openrouter' ? 'sk-or-v1-...' :
                    provider === 'openai' ? 'sk-proj-...' :
                    'Enter API Key / Bearer Token...'
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-emerald-400 focus:outline-none focus:border-cyan-500"
                />
              </div>

              {/* Role */}
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Model Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-cyan-500"
                >
                  <option value="test_agent_ai">Test Agent AI (Agent under evaluation uses this)</option>
                  <option value="user_connected_model">User Benchmark Model (Comparison suite)</option>
                </select>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-3 pt-2">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={testing}
                  className="flex-1 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-mono font-semibold flex items-center justify-center space-x-1.5 transition"
                >
                  <Activity className={`w-3.5 h-3.5 ${testing ? 'animate-spin' : 'text-cyan-400'}`} />
                  <span>{testing ? 'Testing Ping...' : 'Test Connection'}</span>
                </button>

                <button
                  type="submit"
                  className="flex-1 px-3 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-mono font-bold flex items-center justify-center space-x-1.5 shadow-md shadow-cyan-500/20 transition"
                >
                  <Server className="w-3.5 h-3.5" />
                  <span>Save Connection</span>
                </button>
              </div>
            </form>

            {/* Test Result Card */}
            {testResult && (
              <div
                className={`mt-4 p-3.5 rounded-xl border text-xs font-mono ${
                  testResult.success
                    ? 'bg-emerald-950/20 border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-950/20 border-rose-500/40 text-rose-300'
                }`}
              >
                <div className="flex items-center space-x-2 font-bold">
                  {testResult.success ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-rose-400" />
                  )}
                  <span>Status: {testResult.status}</span>
                  {testResult.latency_ms && (
                    <span className="text-[10px] text-slate-400">({testResult.latency_ms}ms)</span>
                  )}
                </div>
                <p className="mt-1 text-[11px] opacity-90">{testResult.message}</p>
                {testResult.details?.sample_response && (
                  <div className="mt-2 p-2 rounded bg-slate-950/80 border border-slate-800 text-[10px] text-slate-300 overflow-x-auto">
                    <code>{testResult.details.sample_response}</code>
                  </div>
                )}
              </div>
            )}

            {error && (
              <div className="mt-4 p-3 rounded-lg border border-rose-500/40 bg-rose-950/20 text-rose-300 text-xs font-mono">
                {error}
              </div>
            )}

            {successMsg && (
              <div className="mt-4 p-3 rounded-lg border border-emerald-500/40 bg-emerald-950/20 text-emerald-300 text-xs font-mono">
                {successMsg}
              </div>
            )}
          </div>
        </div>

        {/* Right: Active Connections List */}
        <div className="lg:col-span-7 space-y-4">
          <h2 className="text-xs font-mono uppercase text-slate-400 tracking-wider">
            Connected Model Endpoints ({connections.length})
          </h2>

          {connections.length === 0 ? (
            <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-900/30 text-slate-400 space-y-3">
              <Server className="w-8 h-8 mx-auto text-slate-600" />
              <p className="text-sm font-mono">No custom or local model connections registered yet.</p>
              <p className="text-xs text-slate-500">
                Register an Ollama or vLLM endpoint to test your agent against local LLMs.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {connections.map((conn) => (
                <div
                  key={conn.id}
                  className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-900 transition space-y-3"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-sm text-slate-100 font-mono">{conn.name}</span>
                        <span className="px-2 py-0.5 text-[10px] font-mono uppercase rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                          {conn.provider}
                        </span>
                        {conn.is_local && (
                          <span className="px-1.5 py-0.5 text-[9px] font-mono uppercase rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                            LOCAL
                          </span>
                        )}
                      </div>
                      <p className="text-xs font-mono text-slate-400 mt-1">
                        <code>{conn.model_identifier}</code> &bull; <span className="text-slate-500">{conn.base_url}</span>
                      </p>
                    </div>

                    <div className="flex items-center space-x-2">
                      <span
                        className={`px-2 py-0.5 text-[10px] font-mono uppercase rounded-full border ${
                          conn.health_status === 'HEALTHY'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                            : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                        }`}
                      >
                        {conn.health_status}
                      </span>
                      <button
                        onClick={() => handleDelete(conn.id)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 rounded-lg hover:bg-slate-800 transition"
                        title="Delete connection"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800 text-[11px] font-mono text-slate-400">
                    <div>
                      <span className="text-slate-600 block text-[9px]">ROLE</span>
                      <span className="text-slate-300">{conn.role}</span>
                    </div>
                    <div>
                      <span className="text-slate-600 block text-[9px]">LATENCY</span>
                      <span className="text-cyan-400">{conn.latency_ms ? `${conn.latency_ms}ms` : 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-slate-600 block text-[9px]">STRUCTURED JSON</span>
                      <span className={conn.supports_structured_json ? 'text-emerald-400' : 'text-slate-500'}>
                        {conn.supports_structured_json ? 'Supported' : 'Unchecked'}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
