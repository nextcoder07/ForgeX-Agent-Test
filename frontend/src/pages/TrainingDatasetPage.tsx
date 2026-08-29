import React, { useState, useEffect } from 'react';
import {
  Layers,
  Database,
  Download,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  FileCode,
  GitCompare,
  Plus,
  RefreshCw,
  Terminal,
  ShieldCheck,
  ChevronRight,
} from 'lucide-react';
import {
  listTrainingDatasets,
  generateTrainingDataset,
  getExportDatasetUrl,
  getExportTrainingPackageUrl,
  fetchAgents,
} from '../api/client';
import type { TrainingDataset, AgentRecord } from '../api/client';

export const TrainingDatasetPage: React.FC = () => {
  const [datasets, setDatasets] = useState<TrainingDataset[]>([]);
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const [datasetName, setDatasetName] = useState<string>('Support_Agent_SFT_DPO_v1');
  const [datasetType, setDatasetType] = useState<string>('HYBRID');
  const [selectedDataset, setSelectedDataset] = useState<TrainingDataset | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadAgents = async () => {
    try {
      const agentList = await fetchAgents();
      setAgents(agentList);
      if (!selectedAgentId && agentList.length > 0) {
        setSelectedAgentId(agentList[0].id);
      }
    } catch (err: any) {
      console.error('Error loading agents:', err);
    }
  };

  const loadDatasetsForAgent = async (agentId: string) => {
    if (!agentId) return;
    setLoading(true);
    try {
      const dsList = await listTrainingDatasets(agentId);
      setDatasets(dsList);
      if (dsList.length > 0) {
        setSelectedDataset(dsList[0]);
      } else {
        setSelectedDataset(null);
      }
    } catch (err: any) {
      console.error('Error loading datasets for agent:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgents();
  }, []);

  useEffect(() => {
    if (selectedAgentId) {
      loadDatasetsForAgent(selectedAgentId);
    }
  }, [selectedAgentId]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAgentId) return;
    setGenerating(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const newDs = await generateTrainingDataset({
        agent_id: selectedAgentId,
        dataset_name: datasetName,
        dataset_type: datasetType,
      });
      setSuccessMsg(`Compiled training dataset '${newDs.name}' with ${newDs.example_count} factual examples!`);
      const updatedList = await listTrainingDatasets();
      setDatasets(updatedList);
      setSelectedDataset(newDs);
    } catch (err: any) {
      setError(err.message || 'Failed to generate training dataset.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-emerald-500/20 to-cyan-500/20 border border-emerald-500/30 text-emerald-400">
              <Database className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-2xl font-extrabold tracking-tight text-white font-mono">
                  TRAINING DATASET BUILDER
                </h1>
                <span className="px-2 py-0.5 text-xs font-mono rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  SFT &bull; DPO &bull; FAILURE RECOVERY
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-0.5">
                Turn execution trajectories and human corrections into high-value training datasets for fine-tuning open-weights models.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={() => {
            loadAgents();
            if (selectedAgentId) loadDatasetsForAgent(selectedAgentId);
          }}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-mono flex items-center space-x-1.5"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Datasets</span>
        </button>
      </div>

      {/* Honest Boundary Alert */}
      <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-950/20 text-xs text-emerald-200 flex items-start space-x-3">
        <ShieldCheck className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-white">Truthful Machine Learning Pipeline</p>
          <p className="mt-0.5 text-emerald-300/90 leading-relaxed">
            ForgeX stores factual user prompts, execution actions, side-effects, and human corrections. These can be exported as standard JSONL datasets to train your own models (e.g. via Hugging Face, Axolotl, Unsloth, or Ollama Modelfiles). ForgeX will never claim to fine-tune third-party proprietary API endpoints.
          </p>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Generator Form */}
        <div className="lg:col-span-4 space-y-6">
          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur-xl">
            <h2 className="text-sm font-bold font-mono text-white flex items-center space-x-2 border-b border-slate-800 pb-3">
              <Plus className="w-4 h-4 text-emerald-400" />
              <span>COMPILE NEW DATASET</span>
            </h2>

            <form onSubmit={handleGenerate} className="space-y-4 mt-4">
              {/* Target Agent */}
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Target Agent</label>
                <select
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-cyan-500"
                >
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.version_label || 'v1.0'})
                    </option>
                  ))}
                </select>
              </div>

              {/* Dataset Name */}
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Dataset Name</label>
                <input
                  type="text"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  required
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-cyan-500"
                />
              </div>

              {/* Dataset Type */}
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Dataset Objective</label>
                <select
                  value={datasetType}
                  onChange={(e) => setDatasetType(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-cyan-500"
                >
                  <option value="HYBRID">Hybrid (SFT + DPO Preference + Recovery)</option>
                  <option value="SFT">Supervised Fine-Tuning (SFT Only)</option>
                  <option value="DPO_PREFERENCE">Direct Preference Optimization (DPO Only)</option>
                  <option value="FAILURE_RECOVERY">Failure Recovery & Self-Correction</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={generating}
                className="w-full mt-2 px-4 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs font-mono flex items-center justify-center space-x-2 shadow-md shadow-emerald-500/20 transition"
              >
                <Sparkles className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
                <span>{generating ? 'Compiling Dataset...' : 'Compile From Evaluation Runs'}</span>
              </button>
            </form>

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

          {/* Dataset Library List */}
          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase text-slate-400 tracking-wider">
              Saved Datasets ({datasets.length})
            </h3>
            {datasets.map((ds) => (
              <div
                key={ds.id}
                onClick={() => setSelectedDataset(ds)}
                className={`p-3.5 rounded-xl border cursor-pointer transition ${
                  selectedDataset?.id === ds.id
                    ? 'bg-slate-800/90 border-emerald-500/80 shadow-md shadow-emerald-500/10'
                    : 'bg-slate-900/50 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-slate-200 font-mono">{ds.name}</span>
                  <span className="px-2 py-0.5 text-[9px] font-mono rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    {ds.dataset_type}
                  </span>
                </div>
                <div className="flex items-center justify-between mt-2 text-[11px] font-mono text-slate-400">
                  <span>{ds.example_count} examples</span>
                  <ChevronRight className="w-3.5 h-3.5 text-emerald-400" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Dataset Viewer & JSONL Exporter */}
        <div className="lg:col-span-8">
          {selectedDataset ? (
            <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur-xl space-y-6">
              {/* Top Header & Download Buttons */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="px-2.5 py-0.5 text-xs font-mono rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                      {selectedDataset.dataset_type}
                    </span>
                    <span className="text-xs font-mono text-slate-400">{selectedDataset.format} FORMAT</span>
                  </div>
                  <h2 className="text-xl font-bold text-white mt-1 font-mono">{selectedDataset.name}</h2>
                  <p className="text-xs text-slate-400 mt-0.5">{selectedDataset.description}</p>
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-950/80 text-cyan-300 border border-cyan-500/30">70% Train</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-950/80 text-amber-300 border border-amber-500/30">15% Validation</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-950/80 text-indigo-300 border border-indigo-500/30">15% Held-Out Benchmark</span>
                  </div>
                </div>

                {/* Export Format Buttons */}
                <div className="flex items-center flex-wrap gap-2">
                  <a
                    href={getExportTrainingPackageUrl(selectedDataset.id)}
                    download
                    className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-slate-950 font-extrabold text-xs font-mono flex items-center space-x-1.5 shadow-md shadow-cyan-500/20 transition cursor-pointer"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download Training Package (ZIP)</span>
                  </a>
                  <a
                    href={getExportDatasetUrl(selectedDataset.id, 'ALL')}
                    download
                    className="px-2.5 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 font-bold text-xs font-mono flex items-center space-x-1 transition cursor-pointer"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>JSONL</span>
                  </a>
                  <a
                    href={`/api/datasets/export?format=sharegpt`}
                    download
                    className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-mono font-bold flex items-center space-x-1 transition cursor-pointer"
                  >
                    <span>ShareGPT</span>
                  </a>
                  <a
                    href={`/api/datasets/export?format=alpaca`}
                    download
                    className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-mono font-bold flex items-center space-x-1 transition cursor-pointer"
                  >
                    <span>Alpaca</span>
                  </a>
                </div>
              </div>

              {/* Breakdown Stats */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-xl border border-slate-800 bg-slate-950 text-center">
                  <span className="text-[10px] text-slate-400 font-mono">SFT EXAMPLES</span>
                  <p className="text-xl font-bold text-cyan-400 font-mono mt-0.5">
                    {selectedDataset.sft_examples.length}
                  </p>
                </div>
                <div className="p-3 rounded-xl border border-slate-800 bg-slate-950 text-center">
                  <span className="text-[10px] text-slate-400 font-mono">PREFERENCE (DPO) PAIRS</span>
                  <p className="text-xl font-bold text-amber-400 font-mono mt-0.5">
                    {selectedDataset.preference_pairs.length}
                  </p>
                </div>
                <div className="p-3 rounded-xl border border-slate-800 bg-slate-950 text-center">
                  <span className="text-[10px] text-slate-400 font-mono">RECOVERY EXAMPLES</span>
                  <p className="text-xl font-bold text-indigo-400 font-mono mt-0.5">
                    {selectedDataset.recovery_examples.length}
                  </p>
                </div>
              </div>

              {/* Sample DPO / SFT Preview Tabs */}
              <div className="space-y-4">
                <h3 className="text-xs font-mono uppercase text-slate-400 tracking-wider">
                  Dataset Sample Records Preview
                </h3>

                {/* Preference Pairs Preview */}
                {selectedDataset.preference_pairs.slice(0, 3).map((pair, idx) => (
                  <div key={idx} className="p-4 rounded-xl border border-slate-800 bg-slate-950 space-y-3">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="text-amber-400 font-bold">DPO Preference Pair #{idx + 1}</span>
                      <span className="text-slate-500">Margin: {pair.margin}x</span>
                    </div>

                    <div className="text-xs font-mono text-slate-300 bg-slate-900 p-2.5 rounded border border-slate-800">
                      <span className="text-slate-500 block mb-1">PROMPT / CONTEXT:</span>
                      <code>{pair.prompt}</code>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                      <div className="p-3 rounded bg-emerald-950/20 border border-emerald-500/30 text-emerald-300">
                        <span className="text-emerald-400 font-bold block mb-1">✓ CHOSEN (SAFE/CORRECT):</span>
                        <p>{pair.chosen}</p>
                      </div>

                      <div className="p-3 rounded bg-rose-950/20 border border-rose-500/30 text-rose-300">
                        <span className="text-rose-400 font-bold block mb-1">✗ REJECTED (UNSAFE/FLAWED):</span>
                        <p>{pair.rejected}</p>
                      </div>
                    </div>

                    <p className="text-[11px] text-slate-400 font-mono italic">
                      Reason: {pair.reason}
                    </p>
                  </div>
                ))}

                {/* SFT Preview */}
                {selectedDataset.sft_examples.slice(0, 2).map((sft, idx) => (
                  <div key={idx} className="p-4 rounded-xl border border-slate-800 bg-slate-950 space-y-2 text-xs font-mono">
                    <div className="flex items-center justify-between text-cyan-400 font-bold">
                      <span>SFT Example #{idx + 1} ({sft.category})</span>
                    </div>
                    {sft.messages.map((m, mIdx) => (
                      <div key={mIdx} className="p-2 rounded bg-slate-900/80 border border-slate-800">
                        <span className="text-slate-500 uppercase text-[10px] block font-bold">{m.role}:</span>
                        <p className="text-slate-200 mt-0.5">{m.content}</p>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-900/30 text-slate-500">
              <p className="text-sm font-mono">Select a dataset on the left or compile a new one from evaluation runs.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
