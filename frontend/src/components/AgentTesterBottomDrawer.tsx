import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Activity,
  CheckCircle2,
  AlertTriangle,
  ChevronUp,
  ChevronDown,
  RefreshCw,
  Cpu,
  Zap,
  Terminal,
  FileCode,
  Sliders,
  Scale,
  Wrench,
  Layers,
  Sparkles,
  Download,
  Users,
  Code2,
  BookOpen,
} from 'lucide-react';
import {
  StageAuditVerdict,
  StageTesterHealth,
  MultiAgentAuditVerdict,
  fetchStageTesterHealth,
  listStageAudits,
  runStageAudit,
  runMultiAgentAudit,
  fetchAgents,
  AgentRecord,
} from '../api/client';

interface AgentTesterBottomDrawerProps {
  currentAgent?: AgentRecord | null;
}

const STAGES = [
  { id: 'analysis', label: '1. Intake Analysis', modelKey: 'intake', icon: FileCode },
  { id: 'scenarios', label: '2. Scenario Gen', modelKey: 'scenarios', icon: Sliders },
  { id: 'execution', label: '3. Sandbox Exec', modelKey: 'execution', icon: Terminal },
  { id: 'evaluation', label: '4. Scorecard Judge', modelKey: 'evaluation', icon: Scale },
  { id: 'repair', label: '5. Remediation Patch', modelKey: 'repair', icon: Wrench },
];

export const AgentTesterBottomDrawer: React.FC<AgentTesterBottomDrawerProps> = ({ currentAgent }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedStage, setSelectedStage] = useState('analysis');
  const [audits, setAudits] = useState<Record<string, StageAuditVerdict>>({});
  const [multiAudit, setMultiAudit] = useState<MultiAgentAuditVerdict | null>(null);
  const [health, setHealth] = useState<StageTesterHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'verdict' | 'training_dataset' | 'remediation'>('verdict');

  // Multi-agent selection state
  const [allAgents, setAllAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentIds, setSelectedAgentIds] = useState<Set<string>>(new Set());

  // Load health, agents, and audits
  const loadData = async () => {
    try {
      const [h, agentsList] = await Promise.all([
        fetchStageTesterHealth(),
        fetchAgents().catch(() => []),
      ]);
      setHealth(h);
      setAllAgents(agentsList);

      if (selectedAgentIds.size === 0 && agentsList.length > 0) {
        if (currentAgent?.id) {
          setSelectedAgentIds(new Set([currentAgent.id]));
        } else {
          setSelectedAgentIds(new Set(agentsList.map((a) => a.id)));
        }
      }

      if (currentAgent?.id) {
        const auditList = await listStageAudits(currentAgent.id);
        const map: Record<string, StageAuditVerdict> = {};
        for (const a of auditList) {
          const key = a.stage_name.toLowerCase();
          if (!map[key]) {
            map[key] = a;
          }
        }
        setAudits(map);
      }
    } catch (e) {
      console.warn('Failed to load agent tester data', e);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 12000);
    return () => clearInterval(interval);
  }, [currentAgent?.id]);

  const toggleAgentSelection = (agentId: string) => {
    const next = new Set(selectedAgentIds);
    if (next.has(agentId)) {
      if (next.size > 1) next.delete(agentId);
    } else {
      next.add(agentId);
    }
    setSelectedAgentIds(next);
  };

  const selectAllAgents = () => {
    if (selectedAgentIds.size === allAgents.length) {
      if (currentAgent) setSelectedAgentIds(new Set([currentAgent.id]));
    } else {
      setSelectedAgentIds(new Set(allAgents.map((a) => a.id)));
    }
  };

  // Run single or multi-agent audit
  const handleRunAudit = async (stageId: string) => {
    setLoading(true);
    try {
      if (selectedAgentIds.size > 1 || !currentAgent) {
        const res = await runMultiAgentAudit({
          agent_ids: Array.from(selectedAgentIds),
          stage_name: stageId,
        });
        setMultiAudit(res);
      } else {
        let inputData: Record<string, any> = {};
        let resultData: Record<string, any> = {};

        if (stageId === 'analysis') {
          inputData = {
            files_count: Object.keys(currentAgent.source_files || {}).length,
            files_list: Object.keys(currentAgent.source_files || {}),
            system_prompt: currentAgent.system_prompt,
          };
          resultData = {
            name: currentAgent.name,
            domain: currentAgent.domain,
            tools_count: currentAgent.tools?.length || 0,
            tools: currentAgent.tools?.map((t) => t.name),
            never_rules: currentAgent.constitution?.never_rules || [],
          };
        } else if (stageId === 'scenarios') {
          inputData = {
            agent_name: currentAgent.name,
            tools: currentAgent.tools?.map((t) => t.name),
          };
          resultData = {
            target_coverage: ['Normal', 'Edge', 'Adversarial', 'Fault Injection', 'Safety Invariants'],
            status: 'GENERATED',
          };
        } else {
          inputData = { agent_id: currentAgent.id };
          resultData = { status: 'COMPLETED' };
        }

        const verdict = await runStageAudit({
          agent_id: currentAgent.id,
          stage_name: stageId,
          input_data: inputData,
          result_data: resultData,
        });

        setAudits((prev) => ({ ...prev, [stageId.toLowerCase()]: verdict }));
      }
    } catch (err) {
      console.error('Failed to trigger stage audit', err);
    } finally {
      setLoading(false);
    }
  };

  // Download fine-tuning dataset as JSONL
  const handleDownloadDataset = () => {
    if (!multiAudit || !multiAudit.training_dataset || multiAudit.training_dataset.length === 0) return;
    const jsonl = multiAudit.training_dataset.map((rec) => JSON.stringify(rec)).join('\n');
    const blob = new Blob([jsonl], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `forgex_${selectedStage}_local_llm_sft_dataset.jsonl`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const activeAudit = audits[selectedStage.toLowerCase()];
  const currentFallbackModel =
    health?.stage_fallback_models?.[selectedStage] || health?.local_model_name || 'qwen2.5-coder:7b';

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 transition-all duration-300 font-sans pointer-events-auto">
      {/* Bottom Bar Header / Collapsed Strip */}
      <div className="bg-[#0b101b]/95 backdrop-blur-xl border-t border-slate-800/80 px-4 py-2.5 flex items-center justify-between shadow-2xl shadow-black/80">
        {/* Left: Status & Model Indicators */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <ShieldCheck className="w-4 h-4 text-emerald-400 animate-pulse" />
            <span className="text-xs font-semibold tracking-wide uppercase">Agent Tester</span>
          </div>

          <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400">
            <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 font-mono text-[11px] text-slate-300">
              <Cpu className="w-3 h-3 text-cyan-400" />
              {health?.configured_model || 'gemini-3.6-flash'}
            </span>

            <span className="flex items-center gap-1 text-[11px] text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-800/50">
              <Zap className="w-3 h-3" />
              Fallback: {currentFallbackModel}
            </span>
          </div>
        </div>

        {/* Center: Stage Quick Badges */}
        <div className="flex items-center gap-1.5 overflow-x-auto max-w-xl py-0.5">
          {STAGES.map((stg) => {
            const audit = audits[stg.id.toLowerCase()];
            const isSelected = selectedStage === stg.id;
            let statusColor = 'text-slate-400 bg-slate-800/50 border-slate-700/50';
            if (audit) {
              if (audit.status === 'PASS') statusColor = 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
              else if (audit.status === 'WARNING') statusColor = 'text-amber-400 bg-amber-500/10 border-amber-500/30';
              else statusColor = 'text-rose-400 bg-rose-500/10 border-rose-500/30';
            }

            return (
              <button
                key={stg.id}
                onClick={() => {
                  setSelectedStage(stg.id);
                  if (!isOpen) setIsOpen(true);
                }}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-all ${statusColor} ${
                  isSelected && isOpen ? 'ring-1 ring-emerald-400 ring-offset-1 ring-offset-[#0b101b]' : 'hover:opacity-80'
                }`}
              >
                <stg.icon className="w-3 h-3" />
                <span className="hidden md:inline">{stg.label.split(' ')[1]}</span>
                {audit ? (
                  <span className="font-mono text-[10px] font-bold px-1 rounded bg-black/40">
                    {audit.score}%
                  </span>
                ) : (
                  <span className="text-[10px] text-slate-500">Ready</span>
                )}
              </button>
            );
          })}
        </div>

        {/* Right: Drawer Controls & Multi-Audit Trigger */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleRunAudit(selectedStage)}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-600/30 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">
              Audit {selectedAgentIds.size > 1 ? `(${selectedAgentIds.size} Agents)` : 'Stage'}
            </span>
          </button>

          <button
            onClick={() => setIsOpen(!isOpen)}
            className="flex items-center gap-1 px-3 py-1 text-xs font-semibold text-slate-300 bg-slate-800/80 hover:bg-slate-700/80 rounded border border-slate-700/80 transition-all"
          >
            <span>{isOpen ? 'Minimize' : 'Inspect Input vs Result'}</span>
            {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Expanded Content Panel */}
      {isOpen && (
        <div className="bg-[#090d16]/98 backdrop-blur-2xl border-t border-slate-800 max-h-[520px] overflow-y-auto p-5 text-slate-200">
          <div className="max-w-7xl mx-auto space-y-4">
            {/* Header: Multi-Agent Selector Bar & Mode Tabs */}
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800/70">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                    {STAGES.find((s) => s.id === selectedStage)?.label} Multi-Agent Judge
                    {multiAudit ? (
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                          multiAudit.overall_status === 'PASS'
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                        }`}
                      >
                        {multiAudit.overall_status} • {multiAudit.overall_score}% Aggregate Score
                      </span>
                    ) : activeAudit ? (
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                          activeAudit.status === 'PASS'
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                        }`}
                      >
                        {activeAudit.status} • {activeAudit.score}% Score
                      </span>
                    ) : null}
                  </h3>
                  <p className="text-xs text-slate-400">
                    Audits website stage fidelity across selected test agents and synthesizes local fine-tuning data.
                  </p>
                </div>
              </div>

              {/* Navigation Tabs (Verdict / Training Dataset / Prompt Remediation) */}
              <div className="flex items-center gap-2 bg-slate-900/80 p-1 rounded-lg border border-slate-800">
                <button
                  onClick={() => setActiveTab('verdict')}
                  className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                    activeTab === 'verdict' ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/40' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5 inline mr-1" />
                  Audit Verdict
                </button>
                <button
                  onClick={() => setActiveTab('remediation')}
                  className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                    activeTab === 'remediation' ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Code2 className="w-3.5 h-3.5 inline mr-1" />
                  Website Improvements
                </button>
                <button
                  onClick={() => setActiveTab('training_dataset')}
                  className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                    activeTab === 'training_dataset' ? 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/40' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5 inline mr-1" />
                  LLM Training Dataset ({multiAudit?.training_dataset?.length || 0})
                </button>
              </div>
            </div>

            {/* Agent Multi-Selection Chips */}
            {allAgents.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800/80 text-xs">
                <span className="flex items-center gap-1 text-slate-400 font-semibold mr-1">
                  <Users className="w-3.5 h-3.5 text-cyan-400" />
                  Selected Test Agents:
                </span>
                <button
                  onClick={selectAllAgents}
                  className="px-2 py-0.5 rounded text-[10.5px] font-mono font-bold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
                >
                  {selectedAgentIds.size === allAgents.length ? 'Deselect All' : `Select All (${allAgents.length})`}
                </button>
                {allAgents.map((a) => {
                  const isSelected = selectedAgentIds.has(a.id);
                  return (
                    <button
                      key={a.id}
                      onClick={() => toggleAgentSelection(a.id)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-mono font-medium border transition ${
                        isSelected
                          ? 'bg-cyan-950 text-cyan-300 border-cyan-500/50 shadow-sm shadow-cyan-500/20'
                          : 'bg-slate-950/60 text-slate-400 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      {isSelected ? '✓ ' : ''}{a.name}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Tab 1: Multi-Agent Verdict & Comparative Results */}
            {activeTab === 'verdict' && (
              <div className="space-y-4">
                {multiAudit ? (
                  <div className="space-y-4">
                    {/* Executive Summary */}
                    <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-400 font-mono">
                          Cross-Agent Meta-Verdict:
                        </span>
                        <span className="text-xs font-mono text-cyan-400">
                          {multiAudit.agent_count} Agents Evaluated • Latency {multiAudit.latency_ms}ms
                        </span>
                      </div>
                      <p className="text-xs text-slate-200 leading-relaxed font-mono bg-slate-950/60 p-3 rounded-lg border border-slate-850">
                        {multiAudit.overall_improvement_needed}
                      </p>
                    </div>

                    {/* Per-Agent Drilldown Table */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {multiAudit.agent_results.map((ar, idx) => (
                        <div key={idx} className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/80 space-y-2.5">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-slate-100 font-mono">{ar.agent_name}</span>
                            <span
                              className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                                ar.status === 'PASS'
                                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/40'
                                  : 'bg-rose-950 text-rose-300 border border-rose-800/40'
                              }`}
                            >
                              {ar.status} • {ar.score}%
                            </span>
                          </div>

                          <div className="text-[11px] text-slate-400 space-y-1">
                            <p><strong className="text-slate-300">Input:</strong> {ar.input_summary}</p>
                            <p><strong className="text-slate-300">Produced:</strong> {ar.output_summary}</p>
                          </div>

                          {ar.discrepancies.length > 0 && (
                            <div className="space-y-1 pt-1 border-t border-slate-800">
                              <span className="text-[10px] uppercase font-bold text-amber-400">Specific Gaps:</span>
                              <ul className="space-y-0.5 text-xs text-amber-300/90">
                                {ar.discrepancies.map((d, dIdx) => (
                                  <li key={dIdx} className="flex items-start gap-1">
                                    <span className="text-amber-400">›</span>
                                    <span>{d}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : activeAudit ? (
                  /* Single Agent Fallback View */
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/80 space-y-2">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                        <FileCode className="w-3.5 h-3.5 text-blue-400" />
                        <span>Stage Input Provided</span>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60 font-mono">
                        {activeAudit.input_summary}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/80 space-y-2">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Stage Result Produced</span>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60 font-mono">
                        {activeAudit.output_summary}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/80 space-y-2">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                        <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                        <span>Judge Executive Verdict</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                        {activeAudit.summary}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 bg-slate-900/40 rounded-xl border border-slate-800/60 space-y-3">
                    <Activity className="w-8 h-8 text-slate-500 mx-auto animate-pulse" />
                    <h4 className="text-sm font-semibold text-slate-200">No Judge Audit Record for {selectedStage} Yet</h4>
                    <p className="text-xs text-slate-400 max-w-md mx-auto">
                      Click "Audit Stage" to test how our website's agent performed across the selected test agents.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Website Prompt & Code Improvements */}
            {activeTab === 'remediation' && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* System Prompt Improvements */}
                  <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-cyan-400" />
                      Website Agent System Prompt Fixes
                    </h4>
                    <ul className="space-y-2 text-xs text-slate-300">
                      {multiAudit?.system_prompt_recommendations && multiAudit.system_prompt_recommendations.length > 0 ? (
                        multiAudit.system_prompt_recommendations.map((rec, idx) => (
                          <li key={idx} className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 flex items-start gap-2">
                            <span className="text-cyan-400 font-bold">›</span>
                            <span>{rec}</span>
                          </li>
                        ))
                      ) : (
                        <li className="text-slate-500 text-xs">Run a multi-agent audit to synthesize prompt improvement rules.</li>
                      )}
                    </ul>
                  </div>

                  {/* Code & AST Remediation */}
                  <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-2">
                      <Code2 className="w-4 h-4 text-indigo-400" />
                      Website Agent Python / Parser Code Fixes
                    </h4>
                    <ul className="space-y-2 text-xs text-slate-300">
                      {multiAudit?.code_remediation_recommendations && multiAudit.code_remediation_recommendations.length > 0 ? (
                        multiAudit.code_remediation_recommendations.map((rec, idx) => (
                          <li key={idx} className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 flex items-start gap-2">
                            <span className="text-indigo-400 font-bold">›</span>
                            <span>{rec}</span>
                          </li>
                        ))
                      ) : (
                        <li className="text-slate-500 text-xs">Run a multi-agent audit to synthesize code remediation rules.</li>
                      )}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 3: Local LLM Fine-Tuning Dataset */}
            {activeTab === 'training_dataset' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <h4 className="text-xs font-bold text-slate-100 flex items-center gap-2">
                      Dedicated Local Fallback Model Target: <code className="text-emerald-400 font-mono">{currentFallbackModel}</code>
                    </h4>
                    <p className="text-[11px] text-slate-400">
                      SFT / DPO dataset synthesized from multi-agent audits to fine-tune our local fallback model for this stage.
                    </p>
                  </div>

                  {multiAudit?.training_dataset && multiAudit.training_dataset.length > 0 && (
                    <button
                      onClick={handleDownloadDataset}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-900/40 transition"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download JSONL Dataset</span>
                    </button>
                  )}
                </div>

                {multiAudit?.training_dataset && multiAudit.training_dataset.length > 0 ? (
                  <div className="space-y-3">
                    {multiAudit.training_dataset.map((rec, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2 text-xs font-mono">
                        <div className="flex items-center justify-between text-slate-400">
                          <span className="text-cyan-400">Example #{idx + 1} ({rec.stage.toUpperCase()})</span>
                          <span>{rec.agent_id ? `Agent: ${rec.agent_id}` : ''}</span>
                        </div>
                        <div className="p-2 rounded bg-slate-950 border border-slate-850 text-slate-300 text-[11px]">
                          <strong className="text-slate-400">Ideal Target:</strong> {rec.ideal_response}
                        </div>
                        {rec.reasoning_critique && (
                          <p className="text-[11px] text-amber-300/90 italic">Critique: {rec.reasoning_critique}</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 bg-slate-900/40 rounded-xl border border-slate-800/60 space-y-2">
                    <BookOpen className="w-8 h-8 text-slate-500 mx-auto" />
                    <p className="text-xs text-slate-400">No training records generated yet. Run a multi-agent audit to synthesize SFT/DPO datasets.</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

