import React, { useState, useEffect } from 'react';
import JSZip from 'jszip';
import { fetchDemoAgents, fetchDemoAgentFiles, analyzeAgentIntake } from '../api/client';
import type { AgentUnderstandingResult } from '../api/client';
import { CodeFileInspector } from './CodeFileInspector';
import {
  Code,
  FileText,
  Globe,
  Sparkles,
  RefreshCw,
  UploadCloud,
  Folder,
  CheckCircle2,
  Cpu,
  Layers,
} from 'lucide-react';

interface AgentIntakeConsoleProps {
  onAnalysisComplete: (result: AgentUnderstandingResult, sourceFiles: Record<string, string>, endpointUrl?: string, inputType?: string) => void;
}

const SAMPLE_PYTHON_CODE = `class CustomerSupportAgent:
    """
    Autonomous customer support agent for e-commerce order management.
    """
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

    def get_order(self, order_id: str):
        """Lookup order status and shipping details by order ID."""
        return {"order_id": order_id, "status": "PROCESSING", "amount": 4500.0}

    def refund_order(self, order_id: str, amount: float):
        """Process monetary refund for order. NOTE: Code allows arbitrary float amount without parameter validation gate."""
        return {"status": "REFUND_SUCCESS", "order_id": order_id, "amount": amount}

    def cancel_order(self, order_id: str):
        """Cancel order and release inventory permanently."""
        return {"status": "CANCELED", "order_id": order_id}

    def update_address(self, customer_id: str, new_address: str):
        """Update shipping address for customer."""
        return {"status": "UPDATED", "address": new_address}
`;

const SAMPLE_PROMPT = `You are a customer support agent. Help customers resolve issues.
NEVER issue refunds above ₹10,000 without authorization.
NEVER cancel an order without explicit customer confirmation.
Use tools whenever account details are required.`;

export const AgentIntakeConsole: React.FC<AgentIntakeConsoleProps> = ({ onAnalysisComplete }) => {
  const [activeTab, setActiveTab] = useState<'files' | 'code' | 'prompt' | 'endpoint'>('files');
  const [pastedCode, setPastedCode] = useState('');
  const [pastedPrompt, setPastedPrompt] = useState('');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshingList, setRefreshingList] = useState(false);

  const [localAgents, setLocalAgents] = useState<string[]>([]);
  const [selectedLocalAgent, setSelectedLocalAgent] = useState('');
  const [agentMetadata, setAgentMetadata] = useState<Record<string, string>>({});
  const [filesPayload, setFilesPayload] = useState<Record<string, string>>({});
  const [inputType, setInputType] = useState('package');

  const refreshLocalAgents = async () => {
    setRefreshingList(true);
    try {
      const agents = await fetchDemoAgents();
      setLocalAgents(agents);
      if (agents.length > 0 && !selectedLocalAgent) {
        handleSelectLocalAgent(agents[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setRefreshingList(false);
    }
  };

  useEffect(() => {
    refreshLocalAgents();
  }, []);

  const handleSelectLocalAgent = async (agentId: string) => {
    setSelectedLocalAgent(agentId);
    if (!agentId) {
      setFilesPayload({});
      setAgentMetadata({});
      return;
    }
    try {
      const data = await fetchDemoAgentFiles(agentId);
      if (data.files) {
        setFilesPayload(data.files);
      }
      if (data.metadata) {
        setAgentMetadata(data.metadata);
      } else {
        setAgentMetadata({});
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const selectedFiles = Array.from(files);
    const hasZip = selectedFiles.some((file) => file.name.toLowerCase().endsWith('.zip'));
    setInputType(hasZip ? 'zip' : selectedFiles.length === 1 ? 'single_file' : 'folder');
    Promise.all(selectedFiles.map(async (file) => {
      if (file.name.toLowerCase().endsWith('.zip')) {
        const zip = await JSZip.loadAsync(await file.arrayBuffer());
        const entries = await Promise.all(Object.values(zip.files)
          .filter((entry) => !entry.dir)
          .map(async (entry) => [entry.name, await entry.async('string')] as const));
        return Object.fromEntries(entries);
      }
      return { [file.webkitRelativePath || file.name]: await file.text() };
    })).then((fileGroups) => {
      setFilesPayload(Object.assign({}, filesPayload, ...fileGroups));
    }).catch((error) => console.error('Unable to read uploaded files', error));
  };

  const handleAnalyze = async () => {
    setLoading(true);
    try {
      const result = await analyzeAgentIntake({
        files: filesPayload,
        input_type: inputType,
        pasted_code: pastedCode || undefined,
        pasted_prompt: pastedPrompt || undefined,
        endpoint_url: endpointUrl || undefined,
        agent_name_hint: agentMetadata.title || selectedLocalAgent || 'Discovered Agent',
      });
      const sourceFiles = { ...filesPayload };
      if (pastedCode) sourceFiles['pasted_source.py'] = pastedCode;
      if (pastedPrompt) sourceFiles['system_prompt.txt'] = pastedPrompt;
      onAnalysisComplete(result, sourceFiles, endpointUrl || undefined, inputType);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 rounded-2xl glass-panel border border-cyan-500/30 bg-slate-950/90 shadow-2xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-extrabold text-slate-100 flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-cyan-400" />
            <span>Universal Agent Intake & Specification Engine</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Ingest arbitrary agents (ZIP, files, code, prompts, endpoints, or demo laboratory). The engine reconstructs an immutable specification.
          </p>
        </div>

        <button
          onClick={() => {
            setActiveTab('code');
            setPastedCode(SAMPLE_PYTHON_CODE);
            setPastedPrompt(SAMPLE_PROMPT);
          }}
          className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs text-cyan-300 font-semibold transition"
        >
          Load Simple Sample
        </button>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 border-b border-slate-800 pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab('files')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition whitespace-nowrap ${
            activeTab === 'files'
              ? 'bg-cyan-950/50 text-cyan-400 border border-cyan-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Folder className="w-3.5 h-3.5" />
          <span>Demo Lab / Upload ({Object.keys(filesPayload).length} files)</span>
        </button>
        <button
          onClick={() => setActiveTab('code')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition whitespace-nowrap ${
            activeTab === 'code'
              ? 'bg-cyan-950/50 text-cyan-400 border border-cyan-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Code className="w-3.5 h-3.5" />
          <span>Paste Source Code</span>
        </button>
        <button
          onClick={() => setActiveTab('prompt')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition whitespace-nowrap ${
            activeTab === 'prompt'
              ? 'bg-cyan-950/50 text-cyan-400 border border-cyan-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>System Instructions</span>
        </button>
        <button
          onClick={() => setActiveTab('endpoint')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition whitespace-nowrap ${
            activeTab === 'endpoint'
              ? 'bg-cyan-950/50 text-cyan-400 border border-cyan-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Globe className="w-3.5 h-3.5" />
          <span>Connect REST Endpoint</span>
        </button>
      </div>

      {activeTab === 'files' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Demo lab selector */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-300 block">Select Demonstration Agent:</label>
                <button
                  onClick={refreshLocalAgents}
                  disabled={refreshingList}
                  className="text-[10px] text-cyan-400 hover:text-cyan-300 flex items-center space-x-1 font-mono"
                  title="Rescan test-agents directory"
                >
                  <RefreshCw className={`w-3 h-3 ${refreshingList ? 'animate-spin' : ''}`} />
                  <span>Rescan Lab</span>
                </button>
              </div>

              <select
                value={selectedLocalAgent}
                onChange={(e) => handleSelectLocalAgent(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-cyan-300 font-mono text-xs focus:outline-none focus:border-cyan-500 transition font-bold"
              >
                <option value="">-- None (Upload your own) --</option>
                {localAgents.map((a) => (
                  <option key={a} value={a}>
                    📁 {a}
                  </option>
                ))}
              </select>
            </div>

            {/* Custom file uploader */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 block">Or Upload Agent Files from Disk:</label>
              <div className="relative">
                <input
                  type="file"
                  multiple
                  {...({ webkitdirectory: '', directory: '' } as React.InputHTMLAttributes<HTMLInputElement>)}
                  accept=".zip,.py,.ts,.tsx,.js,.jsx,.json,.yaml,.yml,.toml,.txt,.md"
                  onChange={handleFileUpload}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <div className="w-full p-2.5 rounded-xl bg-slate-900 border border-dashed border-slate-700 hover:border-cyan-500 text-slate-400 text-xs flex items-center justify-center space-x-2 transition">
                  <UploadCloud className="w-4 h-4 text-cyan-400" />
                  <span>Click to browse or drag .py, .ts, .yaml files</span>
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Code File Inspector */}
          {Object.keys(filesPayload).length > 0 && (
            <CodeFileInspector
              files={filesPayload}
              metadata={agentMetadata}
              onRemove={(fname) => {
                const updated = { ...filesPayload };
                delete updated[fname];
                setFilesPayload(updated);
              }}
            />
          )}
        </div>
      )}

      {activeTab === 'code' && (
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-400">Agent Python / TS Source Code (AST Parsed):</label>
          <textarea
            value={pastedCode}
            onChange={(e) => setPastedCode(e.target.value)}
            rows={8}
            className="w-full p-3 rounded-xl bg-slate-900 border border-slate-800 text-cyan-300 font-mono text-xs focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition"
            placeholder="Paste agent Python / TS code or tool classes..."
          />
        </div>
      )}

      {activeTab === 'prompt' && (
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-400">System Prompt & Policy Requirements:</label>
          <textarea
            value={pastedPrompt}
            onChange={(e) => setPastedPrompt(e.target.value)}
            rows={8}
            className="w-full p-3 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 font-mono text-xs focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition"
            placeholder="Paste system instructions or README requirements..."
          />
        </div>
      )}

      {activeTab === 'endpoint' && (
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">
              Locally Running Agent Network URL (HTTP / REST / WebSocket):
            </label>
            <p className="text-[11px] text-slate-400 mb-2">
              Connect an agent running locally on your computer or local network. ForgeX will dispatch scenario prompts directly over HTTP.
            </p>
            <input
              type="text"
              value={endpointUrl}
              onChange={(e) => setEndpointUrl(e.target.value)}
              className="w-full p-3 rounded-xl bg-slate-900 border border-slate-700 text-cyan-300 font-mono text-xs focus:outline-none focus:border-cyan-500 transition"
              placeholder="http://localhost:8000/run_agent or http://192.168.1.10:8000"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-[10px] text-slate-500 font-mono uppercase">Quick Presets:</span>
            <button
              type="button"
              onClick={() => setEndpointUrl('http://localhost:8000/run_agent')}
              className="px-2 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-[10px] font-mono text-slate-300"
            >
              localhost:8000/run_agent
            </button>
            <button
              type="button"
              onClick={() => setEndpointUrl('http://localhost:5000/chat')}
              className="px-2 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-[10px] font-mono text-slate-300"
            >
              localhost:5000/chat
            </button>
            <button
              type="button"
              onClick={() => setEndpointUrl('http://localhost:3000/api/agent')}
              className="px-2 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-[10px] font-mono text-slate-300"
            >
              localhost:3000/api/agent
            </button>
          </div>
        </div>
      )}

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-2">
        <span className="text-xs text-slate-400 font-mono">AST Static Parser + Platform AI Reconstructor</span>
        <button
          onClick={handleAnalyze}
          disabled={loading || (!pastedCode && !pastedPrompt && !endpointUrl && Object.keys(filesPayload).length === 0)}
          className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-rose-600 hover:from-cyan-600 hover:to-rose-700 text-slate-100 font-bold text-xs shadow-lg shadow-cyan-500/20 flex items-center space-x-2 transition disabled:opacity-50"
        >
          {loading ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Reconstructing Agent Specification...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Analyze & Reconstruct Specification</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
