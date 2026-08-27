import React, { useState, useEffect } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import {
  AlertTriangle,
  Bug,
  Code2,
  FileText,
  ShieldAlert,
  Terminal,
  Cpu,
  ChevronRight,
  Activity,
  Zap,
  Wrench,
  CheckCircle2,
  HelpCircle,
  Layers,
  ArrowUpRight,
  RefreshCw,
  Info
} from 'lucide-react';
import { fetchDiagnosisReport, fetchAgentDiagnosisReport, fetchExecutionJobs, fetchAgents } from '../api/client';
import type { AgentDiagnosisReport, FailureDiagnosis, ExecutionJob, AgentRecord } from '../api/client';
import { PipelineSequenceTracker } from '../components/PipelineSequenceTracker';

export const DiagnosisPage: React.FC = () => {
  const { jobId } = useParams<{ jobId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const agentIdFromUrl = queryParams.get('agentId');

  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>(agentIdFromUrl || '');
  const [evaluationJobs, setEvaluationJobs] = useState<ExecutionJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>(jobId || '');
  const [report, setReport] = useState<AgentDiagnosisReport | null>(null);
  const [selectedDiagnosis, setSelectedDiagnosis] = useState<FailureDiagnosis | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load agents and evaluation jobs
  useEffect(() => {
    Promise.all([fetchAgents(), fetchExecutionJobs()])
      .then(([agentList, jobs]) => {
        setAgents(agentList);
        setEvaluationJobs(jobs);
        if (!selectedAgentId && agentList.length > 0) {
          setSelectedAgentId(agentList[0].id);
        }
        if (!selectedJobId && jobs.length > 0) {
          setSelectedJobId(jobs[0].id);
        }
      })
      .catch((err) => {
        console.error('Error fetching initial diagnosis data:', err);
      });
  }, []);

  // Fetch or compute diagnosis when selected agent or job changes
  useEffect(() => {
    if (!selectedAgentId && !selectedJobId) return;
    setLoading(true);
    setError(null);

    const loadPromise = selectedJobId
      ? fetchDiagnosisReport(selectedJobId)
      : fetchAgentDiagnosisReport(selectedAgentId);

    loadPromise
      .then((data) => {
        setReport(data);
        if (data.diagnoses && data.diagnoses.length > 0) {
          setSelectedDiagnosis(data.diagnoses[0]);
        } else {
          setSelectedDiagnosis(null);
        }
      })
      .catch((err) => {
        console.error('Error loading diagnosis report:', err);
        // If 404, fallback to structured empty report
        setReport({
          id: `diag-empty-${selectedAgentId}`,
          evaluation_run_id: selectedJobId || '',
          agent_id: selectedAgentId,
          agent_name: agents.find(a => a.id === selectedAgentId)?.name || 'Agent',
          total_failures: 0,
          critical_failures: 0,
          defect_breakdown: {},
          primary_repair_recommendation: 'No failure findings to diagnose',
          diagnoses: [],
          created_at: new Date().toISOString()
        });
      })
      .finally(() => setLoading(false));
  }, [selectedAgentId, selectedJobId]);

  const getDefectBadgeColor = (type: string) => {
    switch (type) {
      case 'CODE_DEFECT':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
      case 'PROMPT_DEFECT':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      case 'POLICY_DEFECT':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/40';
      case 'ENVIRONMENT_DEFECT':
        return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
      case 'MODEL_CAPABILITY_DEFECT':
        return 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40';
      default:
        return 'bg-slate-700 text-slate-300 border-slate-600';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-rose-500/20 to-amber-500/20 border border-rose-500/30 text-rose-400">
              <Bug className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-2xl font-extrabold tracking-tight text-white font-mono">
                  FAILURE DIAGNOSIS
                </h1>
                <span className="px-2 py-0.5 text-xs font-mono rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30">
                  ROOT CAUSE ENGINE
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-0.5">
                Exact explanations of why failures occurred, evidence trace, affected code/prompts, and remediation pathways.
              </p>
            </div>
          </div>
        </div>

        {/* Agent and Evaluation Run Selectors */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-2">
            <label className="text-xs font-mono text-slate-400">Agent:</label>
            <select
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-500"
            >
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name || a.name} · {a.version_label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <label className="text-xs font-mono text-slate-400">Run:</label>
            <select
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="">Latest Evaluation</option>
              {evaluationJobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.agent_name || j.id} ({j.completed_scenarios}/{j.total_scenarios} tests)
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => {
              if (selectedJobId) fetchDiagnosisReport(selectedJobId).then(setReport);
              else if (selectedAgentId) fetchAgentDiagnosisReport(selectedAgentId).then(setReport);
            }}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
            title="Refresh Diagnosis"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {loading && (
        <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-900/40">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-400 mb-4"></div>
          <p className="text-sm font-mono text-slate-400">Extracting AST traces and computing root-cause classifications...</p>
        </div>
      )}

      {error && (
        <div className="p-6 rounded-xl border border-rose-500/40 bg-rose-950/30 text-rose-300 text-sm flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Diagnosis Error</p>
            <p className="mt-1 text-rose-200/80 font-mono text-xs">{error}</p>
          </div>
        </div>
      )}

      {report && !loading && (
        <>
          {/* Summary Stat Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
              <span className="text-xs text-slate-400 font-mono">TOTAL FAILURES</span>
              <p className="text-2xl font-bold text-slate-100 mt-1 font-mono">{report.total_failures}</p>
            </div>
            <div className="p-4 rounded-xl border border-rose-900/40 bg-rose-950/20">
              <span className="text-xs text-rose-400 font-mono">CRITICAL DEFECTS</span>
              <p className="text-2xl font-bold text-rose-300 mt-1 font-mono">{report.critical_failures}</p>
            </div>
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
              <span className="text-xs text-slate-400 font-mono">PRIMARY DEFECT TYPE</span>
              <p className="text-sm font-bold text-cyan-300 mt-2 font-mono">
                {Object.entries(report.defect_breakdown).sort((a, b) => b[1] - a[1])[0]?.[0] || 'NONE'}
              </p>
            </div>
            <div className="p-4 rounded-xl border border-cyan-900/40 bg-cyan-950/20">
              <span className="text-xs text-cyan-400 font-mono">RECOMMENDED ACTION</span>
              <p className="text-sm font-bold text-emerald-300 mt-2 font-mono flex items-center space-x-1">
                <Wrench className="w-4 h-4 inline text-emerald-400" />
                <span>{report.primary_repair_recommendation}</span>
              </p>
            </div>
          </div>

          {/* Tabular Matrix of Failure Root Causes */}
          {report.diagnoses.length > 0 && (
            <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/90 space-y-4 font-mono">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <Bug className="w-4 h-4 text-rose-400" />
                  Root Causes & Failure Attribution Table ({report.diagnoses.length})
                </h3>
                <span className="text-[11px] text-slate-400">Click any row below to inspect deep evidence trace</span>
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-800">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] border-b border-slate-800">
                    <tr>
                      <th className="p-3">Scenario</th>
                      <th className="p-3">Defect Category</th>
                      <th className="p-3">Severity</th>
                      <th className="p-3">Root Cause Diagnosis</th>
                      <th className="p-3">Affected Location</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
                    {report.diagnoses.map((d) => {
                      const isSelected = selectedDiagnosis?.id === d.id;
                      return (
                        <tr
                          key={d.id}
                          onClick={() => setSelectedDiagnosis(d)}
                          className={`hover:bg-slate-800/60 transition cursor-pointer ${
                            isSelected ? 'bg-cyan-950/40 border-l-2 border-cyan-400' : ''
                          }`}
                        >
                          <td className="p-3 font-bold text-slate-200 max-w-[180px] truncate">
                            {d.scenario_title || d.scenario_id}
                          </td>
                          <td className="p-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold border ${getDefectBadgeColor(d.root_cause_type)}`}>
                              {d.root_cause_type.replace('_DEFECT', '')}
                            </span>
                          </td>
                          <td className="p-3">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                              d.severity === 'critical' ? 'bg-rose-950 text-rose-300 border border-rose-500/40' : 'bg-amber-950 text-amber-300 border border-amber-500/40'
                            }`}>
                              {d.severity}
                            </span>
                          </td>
                          <td className="p-3 text-slate-300 max-w-[280px] truncate">
                            {d.title}
                          </td>
                          <td className="p-3 text-cyan-300 text-[11px] truncate max-w-[160px]">
                            {d.affected_source_file ? `${d.affected_source_file}:${d.affected_line_number || 1}` : (d.affected_prompt_section ? 'System Prompt' : 'Runtime')}
                          </td>
                          <td className="p-3 text-right">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/fix-agent?agentId=${report.agent_id}`);
                              }}
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 text-[10px] font-bold transition"
                            >
                              Fix in Stage 7 →
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Main 2-Column Diagnosis Workspace */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left: Diagnoses List */}
            <div className="lg:col-span-5 space-y-3">
              <h2 className="text-xs font-mono uppercase text-slate-400 tracking-wider">
                Detected Root Causes ({report.diagnoses.length})
              </h2>

              {report.diagnoses.length === 0 ? (
                <div className="p-8 rounded-xl border border-emerald-500/30 bg-emerald-950/20 text-center text-emerald-300">
                  <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-400" />
                  <p className="font-semibold text-sm">Clean Run - Zero Failures</p>
                  <p className="text-xs text-slate-400 mt-1">All assertions passed with 100% compliance.</p>
                </div>
              ) : (
                <div className="space-y-2.5 max-h-[750px] overflow-y-auto pr-1">
                  {report.diagnoses.map((diag) => {
                    const isSelected = selectedDiagnosis?.id === diag.id;
                    return (
                      <div
                        key={diag.id}
                        onClick={() => setSelectedDiagnosis(diag)}
                        className={`p-3.5 rounded-xl border cursor-pointer transition-all duration-150 ${
                          isSelected
                            ? 'bg-slate-800/90 border-cyan-500/80 shadow-lg shadow-cyan-500/10'
                            : 'bg-slate-900/50 border-slate-800 hover:border-slate-700 hover:bg-slate-850'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center space-x-2">
                            <span
                              className={`px-2 py-0.5 text-[10px] font-mono uppercase rounded-full border ${getDefectBadgeColor(
                                diag.root_cause_type
                              )}`}
                            >
                              {diag.root_cause_type.replace('_DEFECT', '')}
                            </span>
                            <span
                              className={`px-1.5 py-0.2 text-[9px] font-mono uppercase rounded ${
                                diag.severity === 'critical'
                                  ? 'bg-rose-950 text-rose-300 border border-rose-500/50'
                                  : 'bg-amber-950 text-amber-300 border border-amber-500/50'
                              }`}
                            >
                              {diag.severity}
                            </span>
                          </div>
                        </div>

                        <h3 className="text-sm font-semibold text-slate-200 mt-2 line-clamp-1">{diag.title}</h3>
                        <p className="text-xs text-slate-400 mt-1 line-clamp-2">{diag.what_happened}</p>

                        <div className="flex items-center justify-between mt-3 text-[11px] text-slate-500 font-mono">
                          <span>Scenario: {diag.scenario_title || diag.scenario_id.slice(0, 12)}</span>
                          <ChevronRight className="w-3.5 h-3.5 text-cyan-400" />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Right: Detailed Deep-Dive Card */}
            <div className="lg:col-span-7">
              {selectedDiagnosis ? (
                <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur-xl space-y-6">
                  {/* Top Header */}
                  <div className="border-b border-slate-800 pb-4">
                    <div className="flex items-center space-x-2">
                      <span
                        className={`px-2.5 py-0.5 text-xs font-mono uppercase rounded-full border ${getDefectBadgeColor(
                          selectedDiagnosis.root_cause_type
                        )}`}
                      >
                        {selectedDiagnosis.root_cause_type}
                      </span>
                      <span className="text-xs font-mono text-slate-400">ID: {selectedDiagnosis.id}</span>
                    </div>
                    <h2 className="text-xl font-bold text-white mt-2">{selectedDiagnosis.title}</h2>
                  </div>

                  {/* Narrative Sections */}
                  <div className="space-y-4">
                    {/* What Happened */}
                    <div>
                      <h4 className="text-xs font-mono uppercase text-slate-400 flex items-center space-x-1.5">
                        <Activity className="w-3.5 h-3.5 text-cyan-400" />
                        <span>What Happened</span>
                      </h4>
                      <p className="text-sm text-slate-200 mt-1 bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                        {selectedDiagnosis.what_happened}
                      </p>
                    </div>

                    {/* Why It Happened */}
                    <div>
                      <h4 className="text-xs font-mono uppercase text-amber-400 flex items-center space-x-1.5">
                        <HelpCircle className="w-3.5 h-3.5 text-amber-400" />
                        <span>Why It Happened</span>
                      </h4>
                      <p className="text-sm text-slate-200 mt-1 bg-amber-950/10 p-3 rounded-lg border border-amber-500/20">
                        {selectedDiagnosis.why_it_happened}
                      </p>
                    </div>

                    {/* Root Cause Detail */}
                    <div>
                      <h4 className="text-xs font-mono uppercase text-rose-400 flex items-center space-x-1.5">
                        <Bug className="w-3.5 h-3.5 text-rose-400" />
                        <span>Root Cause Specification</span>
                      </h4>
                      <p className="text-sm text-slate-200 mt-1 bg-rose-950/10 p-3 rounded-lg border border-rose-500/20">
                        {selectedDiagnosis.root_cause_detail}
                      </p>
                    </div>

                    {/* Source Code & Prompt Grounding */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                      <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                        <div className="flex items-center space-x-1.5 text-xs font-mono text-cyan-400">
                          <Code2 className="w-4 h-4" />
                          <span>AFFECTED SOURCE FILE</span>
                        </div>
                        <p className="text-xs font-mono text-slate-200 mt-1">
                          {selectedDiagnosis.affected_source_file || 'agent.py'}
                          {selectedDiagnosis.affected_line_number ? ` (Line ${selectedDiagnosis.affected_line_number})` : ''}
                        </p>
                      </div>

                      <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                        <div className="flex items-center space-x-1.5 text-xs font-mono text-indigo-400">
                          <FileText className="w-4 h-4" />
                          <span>AFFECTED PROMPT SECTION</span>
                        </div>
                        <p className="text-xs font-mono text-slate-200 mt-1">
                          {selectedDiagnosis.affected_prompt_section || 'General System Instructions'}
                        </p>
                      </div>
                    </div>

                    {/* Evidence Events Trace */}
                    {selectedDiagnosis.evidence_events.length > 0 && (
                      <div className="pt-2">
                        <h4 className="text-xs font-mono uppercase text-slate-400 flex items-center space-x-1.5 mb-2">
                          <Terminal className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Execution Evidence Trace</span>
                        </h4>
                        <div className="space-y-1.5 bg-slate-950 p-3 rounded-lg border border-slate-800 max-h-40 overflow-y-auto">
                          {selectedDiagnosis.evidence_events.map((ev, idx) => (
                            <div key={idx} className="text-xs font-mono flex items-start space-x-2 text-slate-300">
                              <span className="text-slate-500">[{ev.event_type}]</span>
                              <span>{ev.summary}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Proposed Fix & Action Button */}
                    <div className="p-4 rounded-xl bg-gradient-to-r from-cyan-950/40 to-indigo-950/40 border border-cyan-500/40 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mt-4">
                      <div>
                        <span className="text-[10px] font-mono uppercase text-cyan-300">
                          Recommended Repair ({selectedDiagnosis.recommended_repair_type})
                        </span>
                        <p className="text-xs text-slate-200 mt-0.5">{selectedDiagnosis.suggested_fix_summary}</p>
                      </div>
                      <button
                        onClick={() => navigate('/fix-agent')}
                        className="px-3.5 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center space-x-1.5 shadow-md shadow-cyan-500/20 flex-shrink-0 transition"
                      >
                        <Wrench className="w-3.5 h-3.5" />
                        <span>Open in Fix My Agent</span>
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-900/30 text-slate-500">
                  <p className="text-sm font-mono">Select a failure diagnosis from the list to inspect root cause details.</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
