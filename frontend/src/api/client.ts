/**
 * Complete REST API Client for the Agent Evaluation & Reliability Platform.
 */

export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

export interface ToolDefinition {
  name: string;
  description: string;
  parameters_schema?: Record<string, any>;
  risk: 'low' | 'medium' | 'high' | 'critical';
  is_destructive?: boolean;
  requires_confirmation?: boolean;
  requires_authorization?: boolean;
  max_amount?: number;
  canonical_capability?: string;
  side_effect_type?: string;
}

export interface DependencyDefinition {
  id: string;
  name: string;
  type: string;
  required: boolean;
  detected_from: string;
  status: string;
}

export interface AgentConstitution {
  goals: string[];
  never_rules: string[];
  always_rules: string[];
  escalation_rules: string[];
  data_policies: string[];
}

export interface AgentRecord {
  id: string;
  name: string;
  display_name?: string | null;
  source_name?: string | null;
  description: string;
  domain: string;
  system_prompt: string;
  tools: ToolDefinition[];
  dependencies: DependencyDefinition[];
  constitution: AgentConstitution;
  endpoint?: string;
  version_label: string;
  artifact_id?: string | null;
  artifact_hash?: string | null;
  source_files?: Record<string, string>;
  created_at: string;
}

export interface ArtifactRecord {
  artifact_id: string;
  artifact_hash: string;
  file_count: number;
  total_bytes: number;
  files_list: string[];
  input_type?: string;
  created_at: string;
}

export interface SpecConflict {
  id: string;
  title: string;
  doc_claim: string;
  code_reality: string;
  risk_level: string;
  explanation: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  risk: string;
  details?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
}

export interface NormalizedAgentSpec {
  identity: Record<string, string>;
  goals: string[];
  instructions: string[];
  tools: ToolDefinition[];
  dependencies: DependencyDefinition[];
  constitution: AgentConstitution;
  capabilities: string[];
  risks: string[];
  state_management: string;
  architecture_components: string[];
}

export interface AgentUnderstandingResult {
  artifact: ArtifactRecord;
  normalized_spec: NormalizedAgentSpec;
  conflicts: SpecConflict[];
  confidence_score: number;
  ambiguities: string[];
  graph_nodes: GraphNode[];
  graph_edges: GraphEdge[];
}

export interface FaultInjection {
  target_tool: string;
  fault_type: string;
  occurrence: number;
}

export interface Scenario {
  id: string;
  agent_id?: string | null;
  version: number;
  category: 'normal' | 'edge' | 'recovery' | 'adversarial' | 'safety' | 'security' | 'stress' | 'chaos';
  title: string;
  purpose: string;
  user_messages: string[];
  initial_state: Record<string, any>;
  required_capabilities: string[];
  fault_injections: FaultInjection[];
  critic_passed: boolean;
  critic_notes?: string;
  validation_status: string;
  rationale: string;
}

export interface StrategyCategoryTarget {
  category: string;
  target_count: number;
  focus_risk: string;
  rationale: string;
}

export interface StrategyPlan {
  agent_id: string;
  agent_name: string;
  total_target: number;
  category_distribution: StrategyCategoryTarget[];
  summary: string;
}

export interface CoverageGapReport {
  total_tools: number;
  exercised_tools: number;
  unexercised_tools: string[];
  category_coverage: Record<string, number>;
  overall_coverage_pct: number;
  gaps_detected: string[];
}

export interface ToolCallRecord {
  id: string;
  sequence: number;
  tool_name: string;
  canonical_capability?: string;
  arguments: Record<string, any>;
  result: Record<string, any>;
  latency_ms: number;
  status: string;
  routing_decision: string;
  injected_fault?: string;
}

export interface StateChange {
  resource_type: string;
  resource_id: string;
  field: string;
  before_value: any;
  after_value: any;
}

export interface SecurityEvent {
  event_type: string;
  severity: string;
  target: string;
  action_taken: string;
  evidence: string;
}

export interface TraceEvent {
  timestamp: string;
  role: string;
  content: string;
  tool_call?: ToolCallRecord;
}

export interface ExecutionTrace {
  id: string;
  scenario_id: string;
  agent_id: string;
  agent_version: string;
  events: TraceEvent[];
  tool_calls: ToolCallRecord[];
  state_changes: StateChange[];
  security_events: SecurityEvent[];
  total_latency_ms: number;
  total_tokens: number;
  is_counterfactual: boolean;
  counterfactual_of?: string;
}

export interface FailureFinding {
  category: string;
  severity: string;
  source: string;
  explanation: string;
  evidence: string;
  confidence: number;
}

export interface RunVerdict {
  trace_id: string;
  scenario_id: string;
  passed: boolean;
  findings: FailureFinding[];
  expected_behavior_met: boolean;
  counterfactual_trace_id?: string;
  counterfactual_passed?: boolean;
  attack_causation_proven: boolean;
}

export interface FailureCluster {
  id: string;
  label: string;
  category: string;
  member_verdict_ids: string[];
  representative_evidence: string;
  count: number;
  severity: string;
  recommended_fix: string;
}

export interface ReliabilityScorecard {
  evaluation_id: string;
  agent_id: string;
  agent_name: string;
  agent_version: string;
  correctness: number;
  safety: number;
  robustness: number;
  tool_discipline: number;
  goal_adherence: number;
  composite: number;
  safety_axis: number;
  capability_axis: number;
  total_scenarios: number;
  passed: number;
  failed: number;
  critical_failures: number;
  judge_agreement_rate: number;
}

export interface RegressionComparison {
  from_agent_id: string;
  from_version: string;
  to_agent_id: string;
  to_version: string;
  safety_delta: number;
  capability_delta: number;
  composite_delta: number;
  resolved_failures: string[];
  new_regressions: string[];
  summary_verdict: string;
}

export interface PipelineStage {
  id: string;
  stage_name: string;
  display_title: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'skipped';
  progress_pct: number;
  duration_ms: number;
  model: string;
  input_tokens: number;
  output_tokens: number;
  retry_count: number;
  details: Record<string, any>;
  error?: string;
}

export interface PipelineRun {
  id: string;
  agent_id: string;
  agent_name: string;
  status: 'running' | 'completed' | 'failed';
  total_stages: number;
  completed_stages: number;
  overall_duration_ms: number;
  stages: PipelineStage[];
  started_at: string;
  completed_at?: string;
}

export interface CalibrationSample {
  id: string;
  scenario_title: string;
  trace_snippet: string;
  gold_label_passed: boolean;
  gold_failure_category: string;
  judge_label_passed: boolean;
  judge_failure_category: string;
  agreed: boolean;
}

export interface CalibrationReport {
  total_samples: number;
  agreed_samples: number;
  agreement_rate: number;
  false_positives: number;
  false_negatives: number;
  samples: CalibrationSample[];
}

export interface LiveAttackResponse {
  attack_trace: ExecutionTrace;
  attack_verdict: RunVerdict;
  counterfactual_trace: ExecutionTrace;
  counterfactual_verdict: RunVerdict;
  attack_causation_proven: boolean;
}

// ── API Fetch Functions ─────────────────────────────────────────────────────

export async function fetchAgents(): Promise<AgentRecord[]> {
  const res = await fetch(`${API_BASE_URL}/agents`);
  if (!res.ok) throw new Error(`Failed to fetch agents: ${res.statusText}`);
  return res.json();
}

export async function fetchDemoAgents(): Promise<string[]> {
  const res = await fetch(`${API_BASE_URL}/intake/local-agents`);
  if (!res.ok) throw new Error(`Failed to fetch demo agents: ${res.statusText}`);
  const data = await res.json();
  return data.local_agents || [];
}

export async function fetchDemoAgentFiles(agentId: string): Promise<{ metadata: Record<string, string>; files: Record<string, string> }> {
  const res = await fetch(`${API_BASE_URL}/intake/local-agents/${agentId}`);
  if (!res.ok) throw new Error(`Failed to fetch demo agent files: ${res.statusText}`);
  return res.json();
}

export async function analyzeAgentIntake(payload: any): Promise<AgentUnderstandingResult> {
  const res = await fetch(`${API_BASE_URL}/intake/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to analyze agent: ${res.statusText}`);
  return res.json();
}

export async function registerNormalizedSpec(
  spec: NormalizedAgentSpec,
  displayName?: string,
  artifact?: ArtifactRecord,
  sourceFiles: Record<string, string> = {},
  endpointUrl?: string,
): Promise<AgentRecord> {
  const res = await fetch(`${API_BASE_URL}/intake/register-spec`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      normalized_spec: spec,
      display_name: displayName,
      artifact,
      source_files: sourceFiles,
      endpoint_url: endpointUrl,
    }),
  });
  if (!res.ok) throw new Error(`Failed to register spec: ${res.statusText}`);
  return res.json();
}

export async function fetchStrategyPlan(agentId: string): Promise<StrategyPlan> {
  const res = await fetch(`${API_BASE_URL}/scenarios/strategy/${agentId}`);
  if (!res.ok) throw new Error(`Failed to fetch strategy plan: ${res.statusText}`);
  return res.json();
}

export async function generateScenarios(agentId: string, count: number = 25): Promise<Scenario[]> {
  const res = await fetch(`${API_BASE_URL}/scenarios/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id: agentId, target_count: count }),
  });
  if (!res.ok) throw new Error(`Failed to generate scenarios: ${res.statusText}`);
  return res.json();
}

export async function fetchScenarioLibrary(agentId?: string): Promise<Scenario[]> {
  const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : '';
  const res = await fetch(`${API_BASE_URL}/scenarios/library${query}`);
  if (!res.ok) throw new Error(`Failed to fetch scenario library: ${res.statusText}`);
  return res.json();
}

export async function fetchCoverageReport(agentId: string): Promise<CoverageGapReport> {
  const res = await fetch(`${API_BASE_URL}/scenarios/coverage/${agentId}`);
  if (!res.ok) throw new Error(`Failed to fetch coverage report: ${res.statusText}`);
  return res.json();
}

export async function runEvaluationJob(agentId: string, batchSize: number = 25): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/evaluations/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      scenario_batch_size: batchSize,
      include_counterfactuals: true,
    }),
  });
  if (!res.ok) throw new Error(`Failed to run evaluation job: ${res.statusText}`);
  return res.json();
}

export async function fetchScorecard(evalId: string): Promise<ReliabilityScorecard> {
  const res = await fetch(`${API_BASE_URL}/evaluations/${evalId}/scorecard`);
  if (!res.ok) throw new Error(`Failed to fetch scorecard: ${res.statusText}`);
  return res.json();
}

export async function fetchFailureClusters(evalId: string): Promise<FailureCluster[]> {
  const res = await fetch(`${API_BASE_URL}/evaluations/${evalId}/clusters`);
  if (!res.ok) throw new Error(`Failed to fetch failure clusters: ${res.statusText}`);
  return res.json();
}

export async function compareRegressions(fromId: string, toId: string): Promise<RegressionComparison> {
  const res = await fetch(`${API_BASE_URL}/evaluations/regression/compare?from_job_id=${fromId}&to_job_id=${toId}`);
  if (!res.ok) throw new Error(`Failed to compare regressions: ${res.statusText}`);
  return res.json();
}

export async function runLiveAttack(prompt: string, agentId: string = 'agent-cust-v1'): Promise<LiveAttackResponse> {
  const res = await fetch(`${API_BASE_URL}/live-attack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id: agentId, attack_prompt: prompt }),
  });
  if (!res.ok) throw new Error(`Failed to run live attack: ${res.statusText}`);
  return res.json();
}

export async function fetchCalibrationReport(): Promise<CalibrationReport> {
  const res = await fetch(`${API_BASE_URL}/calibration`);
  if (!res.ok) throw new Error(`Failed to fetch calibration report: ${res.statusText}`);
  return res.json();
}

export async function fetchPipelineRun(runId: string = 'default'): Promise<PipelineRun> {
  const res = await fetch(`${API_BASE_URL}/pipeline/runs/${runId}`);
  if (!res.ok) throw new Error(`Failed to fetch pipeline run: ${res.statusText}`);
  return res.json();
}
