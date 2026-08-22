import React, { useState } from 'react';
import { AgentIntakeConsole } from '../components/AgentIntakeConsole';
import { AgentMapGraph } from '../components/AgentMapGraph';
import { SpecConflictCard } from '../components/SpecConflictCard';
import { registerNormalizedSpec } from '../api/client';
import type { AgentUnderstandingResult, AgentRecord } from '../api/client';
import {
  Sparkles,
  CheckCircle2,
  ArrowRight,
  ShieldAlert,
  Network,
  Layers,
  RefreshCw,
  Cpu,
} from 'lucide-react';
import type { PageId } from '../components/Navbar';

interface AgentIntakePageProps {
  onNavigate: (page: PageId) => void;
  onAgentRegistered: (agent: AgentRecord) => void;
}

export const AgentIntakePage: React.FC<AgentIntakePageProps> = ({ onNavigate, onAgentRegistered }) => {
  const [analysisResult, setAnalysisResult] = useState<AgentUnderstandingResult | null>(null);
  const [registeredAgent, setRegisteredAgent] = useState<AgentRecord | null>(null);
  const [displayName, setDisplayName] = useState('');
  const [sourceFiles, setSourceFiles] = useState<Record<string, string>>({});
  const [endpointUrl, setEndpointUrl] = useState<string | undefined>();
  const [inputType, setInputType] = useState('package');
  const [registering, setRegistering] = useState(false);

  const handleAnalysisComplete = (result: AgentUnderstandingResult, uploadedFiles: Record<string, string>, analyzedEndpoint?: string, analyzedInputType?: string) => {
    setAnalysisResult(result);
    setRegisteredAgent(null);
    setDisplayName('');
    setSourceFiles(uploadedFiles);
    setEndpointUrl(analyzedEndpoint);
    setInputType(analyzedInputType || 'package');
  };

  const handleRegister = async () => {
    if (!analysisResult) return;
    setRegistering(true);
    try {
      const agent = await registerNormalizedSpec(
        analysisResult.normalized_spec,
        displayName,
        analysisResult.artifact,
        sourceFiles,
        endpointUrl,
      );
      setRegisteredAgent(agent);
      onAgentRegistered(agent);
    } catch (e) {
      console.error(e);
    } finally {
      setRegistering(false);
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">Agent Intake & Specification Engine</h1>
        <p className="text-sm text-slate-400 mt-1">
          Load any agent from the test laboratory, upload your files, or paste code. The platform reconstructs a complete normalized specification using AST parsing and AI analysis.
        </p>
      </div>

      {/* Intake Console */}
      <AgentIntakeConsole onAnalysisComplete={handleAnalysisComplete} />

      {/* Analysis Results */}
      {analysisResult && (
        <div className="space-y-6">
          {/* Analysis Summary Banner */}
          <div className="p-5 rounded-2xl glass-panel border border-emerald-500/30 bg-emerald-950/10 flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center space-x-3">
              <div className="p-2.5 rounded-xl bg-emerald-500/20 text-emerald-400">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-emerald-300">Specification Reconstructed Successfully</h2>
                <p className="text-[11px] text-slate-400">
                  Confidence: {(analysisResult.confidence_score * 100).toFixed(0)}% ·
                  {analysisResult.normalized_spec.tools.length} tools discovered ·
                  {analysisResult.conflicts.length} conflicts ·
                  {analysisResult.ambiguities.length} ambiguities
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              {!registeredAgent ? (
                <div className="flex items-end gap-2">
                  <label className="text-[10px] text-slate-400">
                    Your agent name (required)
                    <input
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="Enter a unique name"
                      className="mt-1 block w-48 px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-100 focus:outline-none focus:border-cyan-500"
                    />
                  </label>
                  <button
                    onClick={handleRegister}
                    disabled={registering || !displayName.trim()}
                    className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-600 hover:from-emerald-400 hover:to-cyan-500 text-slate-100 font-bold text-xs shadow-lg shadow-emerald-500/20 flex items-center space-x-2 transition disabled:opacity-50"
                  >
                    {registering ? (
                      <><RefreshCw className="w-4 h-4 animate-spin" /><span>Registering...</span></>
                    ) : (
                      <><Cpu className="w-4 h-4" /><span>Register Agent</span></>
                    )}
                  </button>
                </div>
              ) : (
                <div className="flex items-center space-x-2">
                  <span className="px-3 py-1.5 text-xs font-mono font-bold rounded-lg bg-emerald-950 text-emerald-300 border border-emerald-500/40">
                    {registeredAgent.display_name || registeredAgent.name}
                  </span>
                  <span className="text-[10px] text-slate-500">Registered: {registeredAgent.name}</span>
                  <span className="text-[10px] text-slate-500">Analyzed: {registeredAgent.source_name || registeredAgent.name}</span>
                  <button
                    onClick={() => onNavigate('scenarios')}
                    className="px-4 py-2 rounded-xl bg-indigo-950/50 hover:bg-indigo-950 border border-indigo-500/40 text-indigo-300 font-bold text-xs transition flex items-center space-x-2"
                  >
                    <Layers className="w-3.5 h-3.5" />
                    <span>Generate Scenarios</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Discovered Architecture Map */}
          {analysisResult.graph_nodes.length > 0 && (
            <AgentMapGraph
              nodes={analysisResult.graph_nodes}
              edges={analysisResult.graph_edges}
            />
          )}

          {/* Spec Conflicts */}
          <div>
            <div className="flex items-center space-x-2 mb-3">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <h2 className="text-sm font-bold text-slate-100">
                Documentation vs Code Conflict Analysis
              </h2>
            </div>
            <SpecConflictCard conflicts={analysisResult.conflicts} />
          </div>

          {/* Normalized Spec Inspector */}
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
            <h2 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
              <Network className="w-4 h-4 text-cyan-400" />
              <span>Normalized Agent Specification (Platform Internal Representation)</span>
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              {/* Goals */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <span className="font-mono text-[10px] uppercase text-slate-400">Agent Goals</span>
                <ul className="space-y-1">
                  {analysisResult.normalized_spec.goals.map((g, i) => (
                    <li key={i} className="text-slate-300 flex items-start space-x-1.5">
                      <span className="text-cyan-400 shrink-0 mt-0.5">›</span>
                      <span>{g}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Risks */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <span className="font-mono text-[10px] uppercase text-rose-400">Identified Risk Surface</span>
                <ul className="space-y-1">
                  {analysisResult.normalized_spec.risks.map((r, i) => (
                    <li key={i} className="text-rose-300 flex items-start space-x-1.5">
                      <span className="text-rose-400 shrink-0 mt-0.5">⚠</span>
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Tool Inventory */}
            {analysisResult.normalized_spec.tools.length > 0 && (
              <div>
                <span className="font-mono text-[10px] uppercase text-slate-400 block mb-2">Discovered Tools ({analysisResult.normalized_spec.tools.length})</span>
                <div className="flex flex-wrap gap-2">
                  {analysisResult.normalized_spec.tools.map((tool, i) => (
                    <span key={i} className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold border ${
                      tool.risk === 'critical' ? 'bg-rose-950 text-rose-300 border-rose-500/30' :
                      tool.risk === 'high' ? 'bg-amber-950 text-amber-300 border-amber-500/30' :
                      'bg-slate-900 text-slate-300 border-slate-700'
                    }`}>
                      {tool.name} [{tool.risk}]
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
