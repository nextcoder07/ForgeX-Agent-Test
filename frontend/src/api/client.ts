/**
 * Complete REST API Client for the Agent Evaluation & Reliability Platform.
 */

const configuredApiUrl = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
export const API_BASE_URL = configuredApiUrl
  ? (configuredApiUrl.endsWith('/api') ? configuredApiUrl : `${configuredApiUrl}/api`)
  : '/api';

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
  runtime_manifest?: Record<string, any>;
  execution_status?: string;
  input_type?: string;
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
  pipeline_run_id?: string;
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
  finding_id?: string;
  category: string;
  severity: string;
  title?: string;
  description?: string;
  source: string;
  explanation: string;
  evidence: string;
  expected?: string;
  observed?: string;
  remediation?: string;
  execution_step_id?: string;
  event_ids?: string[];
  evidence_type?: string;
  source_location?: string;
  attempted_action?: boolean;
  policy_blocked?: boolean;
  actual_side_effect?: boolean;
  confidence: number;
}

export interface RunVerdict {
  id?: string;
  evaluation_run_id?: string;
  trace_id: string;
  execution_session_id?: string;
  scenario_id: string;
  scenario_version_id?: string;
  status?: string; // "PASS", "FAIL", "BLOCKED", "INCONCLUSIVE", "ERROR", "NOT_APPLICABLE"
  passed: boolean;
  expected_behavior_met: boolean;
  deterministic_score?: number;
  semantic_score?: number | null;
  final_score?: number;
  findings: FailureFinding[];
  evaluation_method?: string;
  counterfactual_trace_id?: string;
  counterfactual_passed?: boolean;
  attack_causation_proven?: boolean;
}

export interface FailureCluster {
  id: string;
  evaluation_id?: string;
  label: string;
  title?: string;
  category: string;
  root_cause_pattern?: string;
  member_verdict_ids: string[];
  verdict_ids?: string[];
  affected_scenarios?: string[];
  representative_evidence: string;
  count: number;
  occurrences?: number;
  severity: string;
  recommended_fix: string;
  remediation_suggestion?: string;
  failure_surface?: string;
  workflow_node?: string;
}

export interface RegressionTest {
  id: string;
  source_evaluation_id: string;
  source_verdict_id: string;
  agent_id: string;
  scenario_id: string;
  failure_category: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | string;
  assertion: Record<string, any>;
  status: 'ACTIVE' | 'PASSED' | 'DEPRECATED' | 'IGNORED' | string;
  created_at: string;
  updated_at: string;
}

export interface TenDimensionScoreBreakdown {
  correctness?: number | null;
  goal_adherence?: number | null;
  safety?: number | null;
  security?: number | null;
  robustness?: number | null;
  tool_discipline?: number | null;
  recovery?: number | null;
  output_quality?: number | null;
  efficiency?: number | null;
  compliance?: number | null;
  task_correctness?: number | null;
  instruction_following?: number | null;
  tool_correctness?: number | null;
  tool_parameter_correctness?: number | null;
  workflow_correctness?: number | null;
  failure_recovery?: number | null;
  response_quality?: number | null;
  overall_score: number;
  applicable_dimensions?: string[];
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
  blocked?: number;
  inconclusive?: number;
  critical_failures: number;
  judge_agreement_rate?: number | null;
  execution_mode?: string;
  model_substitution?: boolean;
  confidence?: string;
  score_formula_version?: string;
  weights?: Record<string, number>;
  provenance?: Record<string, any>;
  dimension_scores?: TenDimensionScoreBreakdown;
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

export async function generateScenarios(
  agentId: string,
  count: number = 25,
  scenarioType?: string,
  difficulty?: string
): Promise<Scenario[]> {
  const res = await fetch(`${API_BASE_URL}/scenarios/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      target_count: count,
      scenario_type: scenarioType,
      difficulty,
    }),
  });
  if (!res.ok) throw new Error(`Failed to generate scenarios: ${res.statusText}`);
  return res.json();
}

export async function startExecutionJob(
  agentId: string,
  scenarioIds: string[],
  includeCounterfactuals: boolean = true,
  runSync: boolean = true
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/executions/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      scenario_ids: scenarioIds,
      include_counterfactuals: includeCounterfactuals,
      run_sync: runSync,
    }),
  });
  if (!res.ok) throw new Error(`Failed to start execution job: ${res.statusText}`);
  return res.json();
}

export async function evaluateExecutionJob(
  executionJobId: string,
  includeCounterfactuals: boolean = true
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/evaluations/evaluate-execution`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      execution_job_id: executionJobId,
      include_counterfactuals: includeCounterfactuals,
    }),
  });
  if (!res.ok) throw new Error(`Failed to evaluate execution job: ${res.statusText}`);
  return res.json();
}

export async function fetchDatasetSummary(agentId?: string): Promise<any> {
  const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : '';
  const res = await fetch(`${API_BASE_URL}/datasets/summary${query}`);
  if (!res.ok) throw new Error(`Failed to fetch dataset summary: ${res.statusText}`);
  return res.json();
}

export function getDatasetExportUrl(agentId?: string, format: string = 'jsonl'): string {
  const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}&format=${format}` : `?format=${format}`;
  return `${API_BASE_URL}/datasets/export${query}`;
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

// ── Dependency Setup Flow Types ─────────────────────────────────────────────

export interface AgentDependency {
  id: string;
  agent_id: string;
  dependency_name: string;
  dependency_type: 'runtime' | 'tool' | 'credential' | 'external_api';
  required: boolean;
  detected_from: string;
}

export interface PlatformResource {
  id: string;
  capability: string;
  provider: string;
  mode: 'sandbox' | 'redirect' | 'simulate' | 'gateway' | 'unsupported';
  status: 'active' | 'inactive';
}

export interface DependencyBindingType {
  id: string;
  agent_id: string;
  dependency_name: string;
  resolution_type: 'platform_sandbox' | 'free_provider' | 'adapter_mock' | 'user_credential' | 'block';
  status: 'ready' | 'user_credential_required' | 'user_oauth_required' | 'unsupported';
  user_value?: string | null;
  created_at: string;
}

// ── Dependency Setup Flow API Methods ───────────────────────────────────────

export async function getAgentDependencies(agentId: string): Promise<AgentDependency[]> {
  const res = await fetch(`${API_BASE_URL}/intake/agents/${agentId}/dependencies`);
  if (!res.ok) throw new Error(`Failed to fetch dependencies: ${res.statusText}`);
  return res.json();
}

export async function getPlatformResources(): Promise<PlatformResource[]> {
  const res = await fetch(`${API_BASE_URL}/intake/platform/resources`);
  if (!res.ok) throw new Error(`Failed to fetch platform resources: ${res.statusText}`);
  return res.json();
}

export async function getAgentBindings(agentId: string): Promise<DependencyBindingType[]> {
  const res = await fetch(`${API_BASE_URL}/intake/agents/${agentId}/bindings`);
  if (!res.ok) throw new Error(`Failed to fetch bindings: ${res.statusText}`);
  return res.json();
}

export async function updateAgentBindings(agentId: string, bindings: DependencyBindingType[]): Promise<DependencyBindingType[]> {
  const res = await fetch(`${API_BASE_URL}/intake/agents/${agentId}/bindings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bindings }),
  });
  if (!res.ok) throw new Error(`Failed to update bindings: ${res.statusText}`);
  return res.json();
}

// ── Activity Log / Red-Teaming Process Monitor ──────────────────────────────

export interface ActivityEvent {
  id: string;
  timestamp: string;
  category: 'LLM' | 'GATEWAY' | 'DEPENDENCY' | 'SANDBOX' | 'INTAKE' | 'EVALUATION';
  action: string;
  detail: string;
  request_summary?: string | null;
  response_summary?: string | null;
  duration_ms?: number | null;
  status: 'success' | 'warning' | 'error' | 'security_alert';
}

export async function fetchActivityEvents(since?: string): Promise<ActivityEvent[]> {
  const query = since ? `?since=${encodeURIComponent(since)}` : '';
  const res = await fetch(`${API_BASE_URL}/activity/events${query}`);
  if (!res.ok) throw new Error(`Failed to fetch activity events: ${res.statusText}`);
  return res.json();
}

// ── Sandbox Execution Job ───────────────────────────────────────────────────

export interface ExecutionJob {
  id: string;
  agent_id: string;
  agent_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  total_scenarios: number;
  completed_scenarios: number;
  scenario_ids: string[];
  created_at: string;
  finished_at?: string | null;
}

export async function runExecutionJob(
  agentId: string,
  scenarioIds: string[],
  includeCounterfactuals: boolean = true
): Promise<ExecutionJob> {
  const res = await fetch(`${API_BASE_URL}/executions/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      scenario_ids: scenarioIds,
      include_counterfactuals: includeCounterfactuals,
    }),
  });
  if (!res.ok) throw new Error(`Failed to start execution job: ${res.statusText}`);
  return res.json();
}

export async function fetchExecutionJobs(): Promise<ExecutionJob[]> {
  const res = await fetch(`${API_BASE_URL}/executions/jobs`);
  if (!res.ok) throw new Error(`Failed to fetch execution jobs: ${res.statusText}`);
  return res.json();
}

export async function fetchExecutionJobDetails(jobId: string): Promise<ExecutionJob> {
  const res = await fetch(`${API_BASE_URL}/executions/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Failed to fetch execution job details: ${res.statusText}`);
  return res.json();
}

export async function fetchExecutionTraces(jobId: string): Promise<ExecutionTrace[]> {
  const res = await fetch(`${API_BASE_URL}/executions/jobs/${jobId}/traces`);
  if (!res.ok) throw new Error(`Failed to fetch execution traces: ${res.statusText}`);
  return res.json();
}

export async function fetchEvaluationJobDetails(jobId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/evaluations/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Failed to fetch evaluation job details: ${res.statusText}`);
  return res.json();
}

export async function fetchEvaluationVerdicts(jobId: string): Promise<any[]> {
  const res = await fetch(`${API_BASE_URL}/evaluations/jobs/${jobId}/verdicts`);
  if (!res.ok) throw new Error(`Failed to fetch evaluation verdicts: ${res.statusText}`);
  return res.json();
}

export async function fetchEvaluationTracesDetails(jobId: string): Promise<any[]> {
  const res = await fetch(`${API_BASE_URL}/evaluations/jobs/${jobId}/traces`);
  if (!res.ok) throw new Error(`Failed to fetch evaluation traces: ${res.statusText}`);
  return res.json();
}


// ── Execution Model Binding & Dependency Resolver Interfaces ───────────────

export interface ExecutionModelBinding {
  id: string;
  execution_id: string;
  original_model: string;
  executed_model: string;
  original_provider: string;
  executed_provider: string;
  mode: 'faithful' | 'compatible' | 'simulation';
  model_substitution: boolean;
  reason: string;
  confidence: string;
  fidelity: 'HIGH' | 'MEDIUM' | 'TEST-SPECIFIC';
  created_at: string;
}

export interface DependencyResolverResult {
  agent_id: string;
  agent_category: 'llm_powered' | 'local_model' | 'rule_based' | 'tool_heavy';
  detected_model_dependencies: any[];
  detected_secrets: any[];
  recommended_mode: 'faithful' | 'compatible' | 'simulation';
  mode_options: any[];
  active_binding?: ExecutionModelBinding;
}


export interface EvaluationReport {
  evaluation_id: string;
  agent_id: string;
  agent_name: string;
  scenario_id?: string;
  original_model: string;
  executed_model: string;
  execution_mode: 'faithful' | 'compatible' | 'simulation';
  model_substitution: boolean;
  confidence: string;
  overall_score: number;
  dimension_scores: TenDimensionScoreBreakdown;
  explainability: string[];
  strengths: string[];
  failures: string[];
  recommendations: string[];
  created_at: string;
}

export async function resolveDependencies(
  agentId: string,
  requestedMode?: string,
  secrets: Record<string, string> = {}
): Promise<DependencyResolverResult> {
  const res = await fetch(`${API_BASE_URL}/dependencies/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      requested_mode: requestedMode,
      provided_secrets: secrets,
    }),
  });
  if (!res.ok) throw new Error(`Failed to resolve dependencies: ${res.statusText}`);
  return res.json();
}

export async function fetchEvaluationReport(evalId: string): Promise<EvaluationReport> {
  const res = await fetch(`${API_BASE_URL}/evaluations/jobs/${evalId}/report`);
  if (!res.ok) throw new Error(`Failed to fetch evaluation report: ${res.statusText}`);
  return res.json();
}

export async function fetchAgentReliability(agentId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/evaluations/agents/${agentId}/reliability`);
  if (!res.ok) throw new Error(`Failed to fetch reliability metrics: ${res.statusText}`);
  return res.json();
}

export async function fetchAgentRegressions(agentId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/evaluations/agents/${agentId}/regressions`);
  if (!res.ok) throw new Error(`Failed to fetch regression suite: ${res.statusText}`);
  return res.json();
}

// ── Fix My Agent Repair Interfaces & API Methods ────────────────────────────

export interface RepairIterationResult {
  iteration: number;
  agent_id: string;
  agent_version: string;
  previous_version: string;
  eval_scorecard: ReliabilityScorecard;
  fixing_agent_reasoning: string;
  changes_made: string[];
  diff_summary: string;
  passed_count: number;
  failed_count: number;
  critical_failures: number;
  status: string; // "IMPROVED" | "REGRESSED" | "PASSED" | "FAILED"
  created_at: string;
}

export interface RepairSession {
  id: string;
  agent_id: string;
  agent_name: string;
  original_version: string;
  current_version: string;
  status: 'IDLE_AWAITING_USER_APPROVAL' | 'RUNNING' | 'COMPLETED_FIXED' | 'COMPLETED_PARTIAL' | 'STOPPED_BY_USER' | 'MAX_ITERATIONS_REACHED' | 'FAILED';
  max_iterations: number;
  current_iteration: number;
  current_step?: string;
  baseline_scorecard?: ReliabilityScorecard | null;
  latest_scorecard?: ReliabilityScorecard | null;
  iterations: RepairIterationResult[];
  final_status: string;
  final_verdict?: string;
  error_message?: string | null;
  user_approved_repair: boolean;
  stop_requested: boolean;
  created_at: string;
  updated_at: string;
}

export async function getAgentRepairStatus(agentId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/repair/agents/${agentId}/status`);
  if (!res.ok) throw new Error(`Failed to fetch repair status: ${res.statusText}`);
  return res.json();
}

export async function startRepairSession(sessionId: string, maxIterations: number = 5): Promise<RepairSession> {
  const res = await fetch(`${API_BASE_URL}/repair/sessions/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, max_iterations: maxIterations }),
  });
  if (!res.ok) throw new Error(`Failed to start repair session: ${res.statusText}`);
  return res.json();
}

export async function stopRepairSession(sessionId: string): Promise<RepairSession> {
  const res = await fetch(`${API_BASE_URL}/repair/sessions/${sessionId}/stop`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to stop repair session: ${res.statusText}`);
  return res.json();
}

export async function getRepairSession(sessionId: string): Promise<RepairSession> {
  const res = await fetch(`${API_BASE_URL}/repair/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to fetch repair session: ${res.statusText}`);
  return res.json();
}

export async function fetchRegressionTests(agentId?: string): Promise<RegressionTest[]> {
  const url = agentId
    ? `${API_BASE_URL}/evaluations/regression-tests?agent_id=${encodeURIComponent(agentId)}`
    : `${API_BASE_URL}/evaluations/regression-tests`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch regression tests: ${res.statusText}`);
  return res.json();
}

export async function createRegressionTest(data: Partial<RegressionTest>): Promise<RegressionTest> {
  const res = await fetch(`${API_BASE_URL}/evaluations/regression-tests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to create regression test: ${res.statusText}`);
  return res.json();
}
