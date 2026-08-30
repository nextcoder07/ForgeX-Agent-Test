/**
 * Complete REST API Client for the Agent Evaluation & Reliability Platform.
 */

const configuredApiUrl = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
export const API_BASE_URL = configuredApiUrl
  ? (configuredApiUrl.endsWith('/api') ? configuredApiUrl : `${configuredApiUrl}/api`)
  : '/api';

// Intercept native fetch in browser to automatically inject active Firebase user token and X-User-ID headers ONLY for ForgeX backend requests
if (typeof window !== 'undefined' && window.fetch) {
  const originalFetch = window.fetch;
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    let urlStr = '';
    if (typeof input === 'string') {
      urlStr = input;
    } else if (input instanceof URL) {
      urlStr = input.toString();
    } else if (input && typeof (input as any).url === 'string') {
      urlStr = (input as any).url;
    }

    // Only inject custom ForgeX headers for backend API requests to avoid CORS preflight rejection by Firebase/Google
    const isBackendCall = 
      urlStr.startsWith('/api') || 
      (API_BASE_URL && urlStr.startsWith(API_BASE_URL)) || 
      urlStr.includes(':8000') || 
      urlStr.startsWith(window.location.origin + '/api');

    if (!isBackendCall) {
      return originalFetch(input, init);
    }

    const token = localStorage.getItem('forgex_active_user_token');
    const userJson = localStorage.getItem('forgex_active_user_session');
    let uid = 'anonymous';
    if (userJson) {
      try {
        uid = JSON.parse(userJson).uid || 'anonymous';
      } catch (e) {}
    }

    const headers = new Headers(init?.headers || {});
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    if (uid && !headers.has('X-User-ID')) {
      headers.set('X-User-ID', uid);
    }

    const activeWsId = localStorage.getItem('forgex_active_workspace_id');
    if (activeWsId && !headers.has('X-Workspace-ID')) {
      headers.set('X-Workspace-ID', activeWsId);
    }

    return originalFetch(input, {
      ...init,
      headers
    });
  };
}

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

export interface PlanningProfile {
  planning_present: boolean;
  planning_type: string;
  planner_component?: string;
  planner_model_slot?: string;
  goal_representation?: string;
  plan_representation?: string;
  plan_steps: string[];
  dynamic_replanning: boolean;
  reflection_present: boolean;
  loop_present: boolean;
  termination_condition?: string;
  max_iterations?: number;
  branching_conditions: string[];
  delegation_present: boolean;
  evidence: string[];
  confidence: number;
}

export interface MemoryProfile {
  memory_present: boolean;
  memory_types: string[];
  storage_backend?: string;
  retrieval_mechanism?: string;
  write_points: string[];
  read_points: string[];
  persistence_scope: string;
  session_scope?: string;
  expiration?: string;
  mutation_behavior: string;
  evidence: string[];
  confidence: number;
}

export interface ContextProfile {
  retrieval_present: boolean;
  retrieval_backend?: string;
  retriever?: string;
  reranker?: string;
  chunking?: string;
  max_context_tokens?: number;
  truncation_rules: string[];
  grounding_rules: string[];
  citation_rules: string[];
  context_sources: string[];
  evidence: string[];
  confidence: number;
}

export interface ToolProfile {
  tool_id: string;
  name: string;
  description: string;
  parameters_schema: Record<string, any>;
  side_effect_type: string;
  is_read_only: boolean;
  destructive: boolean;
  authorization_required: boolean;
  confirmation_required: boolean;
  idempotency: boolean;
  target_service?: string;
  source_evidence: string;
  policy_constraints: string[];
  confidence: number;
}

export interface ExternalServiceProfile {
  service_id: string;
  provider: string;
  endpoint?: string;
  required_credentials: string[];
  availability: string;
  timeout_seconds: number;
  mock_adapter?: string;
  evidence: string;
}

export interface AgentModelSlot {
  slot_id: string;
  agent_id: string;
  role: string;
  name: string;
  code_variable: string;
  source_location: string;
  detected_provider: string;
  detected_model: string;
  model_usage: string;
  required: boolean;
  bound_connection_id: string;
  owner_type: string;
  is_trainable: boolean;
}

export interface LearningProfile {
  learning_present: boolean;
  reflection_enabled: boolean;
  in_context_feedback: boolean;
  self_correction_present: boolean;
  feedback_sources: string[];
  adaptation_mechanisms: string[];
  fine_tuning_eligible: boolean;
  evidence: string[];
}

export interface GovernanceProfile {
  guardrails_present: boolean;
  never_rules: string[];
  always_rules: string[];
  escalation_triggers: string[];
  hallucination_safeguards: string[];
  confirmation_policies: string[];
  prompt_injection_defense: boolean;
  evidence: string[];
}

export interface CommunicationProfile {
  interface_type: string;
  multi_turn_dialogue: boolean;
  intent_classification_present: boolean;
  emotional_tone_constraints: string[];
  output_formatting_rules: string[];
  evidence: string[];
}

export interface CanonicalAgentRepresentation {
  agent_id: string;
  name: string;
  domain: string;
  archetype: string;
  planning: PlanningProfile;
  memory: MemoryProfile;
  context: ContextProfile;
  tools: ToolProfile[];
  external_services: ExternalServiceProfile[];
  model_slots: AgentModelSlot[];
  learning?: LearningProfile;
  governance?: GovernanceProfile;
  communication?: CommunicationProfile;
  data_flows: { source: string; target: string; data_type: string; description?: string }[];
  policies: string[];
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
  runtime_manifest?: Record<string, any>;
  execution_status?: string;
  semantic_status?: string;
  analysis_status?: string;
  canonical_subsystems?: CanonicalAgentRepresentation;
  evidence_packet?: Record<string, any>;
  audit_report?: Record<string, any>;
  decision_surfaces?: any[];
  workflow?: any[];
  inputs?: any[];
  outputs?: any[];
  security_surfaces?: any[];
  side_effects?: string[];
}

export interface AgentUnderstandingResult {
  artifact: ArtifactRecord;
  normalized_spec: NormalizedAgentSpec;
  conflicts: SpecConflict[];
  confidence_score: number;
  ambiguities: string[];
  graph_nodes: GraphNode[];
  graph_edges: GraphEdge[];
  canonical_subsystems?: CanonicalAgentRepresentation;
  pipeline_run_id?: string;
  inferred_description?: string;
  audit_report?: Record<string, any>;
  evidence_packet?: Record<string, any>;
}

export interface FaultInjection {
  target_tool: string;
  fault_type: string;
  occurrence: number;
}

export interface ScenarioAssertion {
  assertion_type: string;
  target?: string;
  expected_value?: any;
  description?: string;
}

export type TargetSubsystem =
  | 'reasoning_planning'
  | 'memory_context'
  | 'tool_execution'
  | 'learning_adaptation'
  | 'governance_security'
  | 'communication_interface';

export interface Scenario {
  id: string;
  agent_id?: string | null;
  version: number;
  category: 'normal' | 'edge' | 'recovery' | 'adversarial' | 'safety' | 'security' | 'stress' | 'chaos';
  target_subsystem?: TargetSubsystem;
  subsystem_evaluation_criteria?: string[];
  context_preconditions?: Record<string, any>;
  expected_subsystem_transitions?: Record<string, any>[];
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
  interface_type?: string;
  invocation?: Record<string, any>;
  assertions?: ScenarioAssertion[];
  target_failure_surface?: string;
  target_invariant?: string;
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
  id?: string;
  sequence?: number;
  tool_name: string;
  canonical_capability?: string;
  arguments: Record<string, any>;
  result?: Record<string, any> | any;
  latency_ms?: number;
  status: string;
  routing_decision?: string;
  policy_reason?: string;
  injected_fault?: string;
}

export interface StateChange {
  resource_type?: string;
  resource_id?: string;
  field?: string;
  before_value?: any;
  after_value?: any;
  actor?: string;
  event_id?: string;
  target?: string;
  path?: string;
  previous_value?: any;
  new_value?: any;
  change_type?: string;
  timestamp?: string;
}

export interface DecisionEvent {
  event_id: string;
  execution_id: string;
  parent_event_id?: string;
  actor_id: string;
  model_slot_id: string;
  decision_type: string;
  input_reference: string;
  selected_action: string;
  action_arguments: Record<string, any>;
  action_rationale_emitted?: string;
  state_before_action?: Record<string, any>;
  state_after_action?: Record<string, any>;
  policy_result: string;
  timestamp: string;
}

export interface MemoryEvent {
  event_id: string;
  execution_id: string;
  operation: string;
  memory_type: string;
  store_id: string;
  query_reference?: string;
  returned_record_ids: string[];
  context_tokens: number;
  timestamp: string;
}

export interface StateTransitionEvent {
  event_id: string;
  execution_id: string;
  from_node: string;
  to_node: string;
  branch_condition?: string;
  trigger: string;
  state_version: number;
  timestamp: string;
}

export interface ExecutionAction {
  id: string;
  action_id?: string;
  execution_session_id: string;
  sequence: number;
  action_type: string;
  target: string;
  action_attempt: { payload?: Record<string, any> };
  policy_decision: { decision?: string; reason?: string };
  execution_result: { status?: string; executed?: boolean };
  side_effect: { detected?: boolean; details?: Record<string, any> };
  timestamp?: string;
}

export interface ObservationSummary {
  action_count?: number;
  tool_calls?: number;
  llm_calls?: number;
  network_requests?: number;
  file_reads?: number;
  file_writes?: number;
  database_operations?: number;
  retries?: number;
  timeouts?: number;
  errors?: number;
  blocked_actions?: number;
  policy_blocks?: number;
  network_blocks?: number;
  unexpected_tool_calls?: number;
  state_changes?: number;
  external_side_effects?: number;
  max_retry_streak?: number;
  execution_duration_ms?: number;
  exit_code?: number;
  files_created?: string[];
  files_modified?: string[];
  emails_sent?: any[];
  database_queries_executed?: string[];
  external_http_calls?: string[];
  policy_violations?: string[];
  total_actions?: number;
}

export interface EvidencePackage {
  session_id: string;
  scenario_id: string;
  agent_version_id: string;
  observation_summary?: ObservationSummary;
  evidence_references: string[];
  trajectory_hash: string;
  sealing_timestamp: string;
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
  decision_events?: DecisionEvent[];
  memory_events?: MemoryEvent[];
  state_transitions?: StateTransitionEvent[];
  actions?: ExecutionAction[];
  observation_summary?: ObservationSummary;
  status?: string;
  total_latency_ms: number;
  total_tokens: number;
  is_counterfactual: boolean;
  counterfactual_of?: string;
  trajectory_hash?: string;
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
  overall_result?: 'PASS' | 'FAIL' | 'PARTIAL' | 'NOT_EVALUABLE' | string;
  status_title?: string;
  status_summary?: string;
  is_healthy_agent?: boolean;
  behavioral_summary?: Record<string, string>;
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

export type SetupState = 'NOT_STARTED' | 'ANALYZING' | 'PREPARING' | 'INSTALLING' | 'VERIFYING' | 'READY' | 'BLOCKED' | 'FAILED';

export interface SetupReadinessRecord {
  id: string;
  agent_id: string;
  agent_version_id: string;
  execution_id?: string | null;
  status: SetupState;
  current_step: string;
  progress_pct: number;
  runtime_status: string;
  dependency_status: string;
  installed_dependencies: string[];
  missing_dependencies: string[];
  credential_status: string;
  missing_credentials: string[];
  model_status: string;
  service_status: string;
  artifact_status: string;
  sandbox_status: string;
  execution_mode: string;
  blockers: { category?: string; message?: string }[];
  created_at: string;
  updated_at: string;
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

export async function purgeAllAgents(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/intake/agents`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to purge workspace: ${res.statusText}`);
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
  if (!res.ok) {
    let errDetail = res.statusText;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      } else if (errJson.message) {
        errDetail = errJson.message;
      }
    } catch {}
    throw new Error(`Failed to register spec (${res.status}): ${errDetail}`);
  }
  return res.json();
}

export async function fetchStrategyPlan(
  agentId: string,
  targetCount: number = 20,
  categoryCounts?: Record<string, number>
): Promise<StrategyPlan> {
  const params = new URLSearchParams();
  params.set('target_count', String(targetCount));
  if (categoryCounts) {
    params.set('category_counts', JSON.stringify(categoryCounts));
  }
  const res = await fetch(`${API_BASE_URL}/scenarios/strategy/${agentId}?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch strategy plan: ${res.statusText}`);
  return res.json();
}

export async function generateScenarios(
  agentId: string,
  count: number = 25,
  scenarioType?: string,
  difficulty?: string,
  categoryCounts?: Record<string, number>
): Promise<Scenario[]> {
  const res = await fetch(`${API_BASE_URL}/scenarios/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      target_count: count,
      scenario_type: scenarioType,
      difficulty,
      category_counts: categoryCounts,
    }),
  });
  if (!res.ok) throw new Error(`Failed to generate scenarios: ${res.statusText}`);
  return res.json();
}

export async function deleteAgent(agentId: string): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE_URL}/agents/${agentId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete agent: ${res.statusText}`);
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
  const res = await fetch(`${API_BASE_URL}/evaluations/jobs/${evalId}/scorecard`);
  if (!res.ok) throw new Error(`Failed to fetch scorecard: ${res.statusText}`);
  return res.json();
}

export async function fetchFailureClusters(evalId: string): Promise<FailureCluster[]> {
  const res = await fetch(`${API_BASE_URL}/evaluations/jobs/${evalId}/clusters`);
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

export async function startFullEvaluationPipeline(
  agentId: string,
  requestedMode: string = 'simulation',
  secrets: Record<string, string> = {},
): Promise<PipelineRun> {
  const res = await fetch(`${API_BASE_URL}/pipeline/run-full-evaluation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id: agentId, requested_mode: requestedMode, secrets }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail?.message || `Failed to start full evaluation: ${res.statusText}`);
  }
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

export interface SystemCredentialItem {
  key_name: string;
  provider: string;
  description: string;
  is_configured: boolean;
  source: 'system_env' | 'user_custom' | 'missing';
  masked_value?: string | null;
}

export interface CredentialRequirement {
  key_name: string;
  provider: string;
  description: string;
  is_fulfilled: boolean;
  is_optional?: boolean;
  provided_by_system?: boolean;
  masked_value?: string | null;
}

export interface SessionCredentialPrompt {
  session_id: string;
  agent_id: string;
  mode: string;
  all_fulfilled: boolean;
  status: string;
  requirements: CredentialRequirement[];
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

export async function getSystemCredentials(): Promise<SystemCredentialItem[]> {
  const res = await fetch(`${API_BASE_URL}/dependencies/system-credentials`);
  if (!res.ok) throw new Error(`Failed to fetch system credentials: ${res.statusText}`);
  return res.json();
}

export async function updateSystemCredentials(credentials: Record<string, string>): Promise<SystemCredentialItem[]> {
  const res = await fetch(`${API_BASE_URL}/dependencies/system-credentials`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credentials }),
  });
  if (!res.ok) throw new Error(`Failed to update system credentials: ${res.statusText}`);
  return res.json();
}

export async function getAgentRequiredCredentials(agentId: string, mode: string = 'faithful'): Promise<SessionCredentialPrompt> {
  const res = await fetch(`${API_BASE_URL}/dependencies/agents/${agentId}/required-credentials?mode=${mode}`);
  if (!res.ok) throw new Error(`Failed to fetch agent credential demands: ${res.statusText}`);
  return res.json();
}

export async function resolveAgentDependencies(agentId: string, requestedMode?: string, secrets?: Record<string, string>): Promise<DependencyResolverResult> {
  const res = await fetch(`${API_BASE_URL}/dependencies/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      requested_mode: requestedMode,
      provided_secrets: secrets || {},
    }),
  });
  if (!res.ok) throw new Error(`Failed to resolve dependencies: ${res.statusText}`);
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
  status: 'pending' | 'running' | 'completed' | 'failed' | 'blocked' | 'BLOCKED';
  error_message?: string;
  total_scenarios: number;
  completed_scenarios: number;
  scenario_ids: string[];
  created_at: string;
  finished_at?: string | null;
}

export async function runExecutionJob(
  agentId: string,
  scenarioIds: string[],
  includeCounterfactuals: boolean = true,
  requestedMode: string = 'faithful'
): Promise<ExecutionJob> {
  const res = await fetch(`${API_BASE_URL}/executions/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      scenario_ids: scenarioIds,
      include_counterfactuals: includeCounterfactuals,
      requested_mode: requestedMode,
    }),
  });
  if (!res.ok) {
    let msg = `Failed to start execution job (${res.status})`;
    try {
      const errData = await res.json();
      msg = errData.detail?.message || (typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail)) || msg;
    } catch {}
    throw new Error(msg);
  }
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

export async function fetchEvaluationJobs(agentId?: string): Promise<any[]> {
  const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : '';
  const res = await fetch(`${API_BASE_URL}/evaluations/jobs${query}`);
  if (!res.ok) throw new Error(`Failed to fetch evaluation jobs: ${res.statusText}`);
  return res.json();
}

export async function fetchEvaluationJobDetails(jobId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/evaluations/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Failed to fetch evaluation job details: ${res.statusText}`);
  return res.json();
}

export async function deleteEvaluationJob(jobId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/evaluations/jobs/${jobId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete evaluation run: ${res.statusText}`);
  return res.json();
}

export async function runPreflightPingTest(agentId: string): Promise<{
  agent_id: string;
  agent_name: string;
  success: boolean;
  status: string;
  latency_ms: number;
  checks: { name: string; status: string; detail: string }[];
}> {
  const res = await fetch(`${API_BASE_URL}/execution/ping-test/${encodeURIComponent(agentId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Ping test failed: ${res.statusText}`);
  return res.json();
}

export async function fetchLatestExecutionJob(agentId: string): Promise<{ job: ExecutionJob | null; traces: ExecutionTrace[] }> {
  try {
    const res = await fetch(`${API_BASE_URL}/executions/latest/${encodeURIComponent(agentId)}`);
    if (!res.ok) return { job: null, traces: [] };
    return res.json();
  } catch (e) {
    return { job: null, traces: [] };
  }
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
  dependency_requirements?: any[];
  detected_secrets: any[];
  recommended_mode: 'faithful' | 'compatible' | 'simulation';
  mode_options: any[];
  active_binding?: ExecutionModelBinding;
  execution_dependency_binding?: any;
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

// ── Failure Diagnosis & Root Cause Analysis Interfaces ──────────────────────

export interface DiagnosticEvidence {
  event_id: string;
  event_type: string;
  timestamp?: string;
  summary: string;
  raw_payload?: Record<string, any>;
}

export interface FailureDiagnosis {
  id: string;
  finding_id: string;
  agent_id: string;
  scenario_id: string;
  scenario_title?: string;
  category: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  root_cause_type: 'CODE_DEFECT' | 'PROMPT_DEFECT' | 'POLICY_DEFECT' | 'ENVIRONMENT_DEFECT' | 'TOOL_DEFECT' | 'MODEL_CAPABILITY_DEFECT';
  what_happened: string;
  why_it_happened: string;
  root_cause_detail: string;
  impact_assessment: string;
  affected_source_file?: string;
  affected_line_number?: number;
  affected_symbol?: string;
  affected_prompt_section?: string;
  evidence_events: DiagnosticEvidence[];
  attempted_action?: string;
  policy_blocked: boolean;
  actual_side_effect_occurred: boolean;
  recommended_repair_type: 'CODE_PATCH' | 'PROMPT_HARDENING' | 'TOOL_POLICY' | 'CONFIG_UPDATE' | 'TRAINING_DATASET';
  suggested_fix_summary: string;
  created_at: string;
}

export interface AgentDiagnosisReport {
  id: string;
  agent_id: string;
  agent_name: string;
  evaluation_run_id: string;
  total_failures: number;
  critical_failures: number;
  diagnoses: FailureDiagnosis[];
  defect_breakdown: Record<string, number>;
  primary_repair_recommendation: string;
  created_at: string;
}

export async function fetchDiagnosisReport(evaluationRunId: string): Promise<AgentDiagnosisReport> {
  const res = await fetch(`${API_BASE_URL}/diagnosis/${encodeURIComponent(evaluationRunId)}`);
  if (!res.ok) throw new Error(`Failed to fetch diagnosis report: ${res.statusText}`);
  return res.json();
}

export async function fetchAgentDiagnosisReport(agentId: string): Promise<AgentDiagnosisReport> {
  const res = await fetch(`${API_BASE_URL}/diagnosis/agent/${encodeURIComponent(agentId)}`);
  if (!res.ok) throw new Error(`Failed to fetch agent diagnosis report: ${res.statusText}`);
  return res.json();
}

// ── Model Connections Interfaces & API Methods ──────────────────────────────

export interface ModelConnection {
  id: string;
  name: string;
  provider: 'ollama' | 'vllm' | 'lm_studio' | 'openai_compatible' | 'custom_http' | 'huggingface';
  base_url: string;
  api_key?: string | null;
  model_identifier: string;
  role: 'platform_ai' | 'test_agent_ai' | 'user_connected_model';
  context_window: number;
  supports_structured_json: boolean;
  supports_tools: boolean;
  is_active: boolean;
  is_local: boolean;
  health_status: 'HEALTHY' | 'UNREACHABLE' | 'ERROR' | 'UNKNOWN';
  last_ping_at?: string | null;
  latency_ms?: number | null;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export interface ModelConnectionTestRequest {
  provider: string;
  base_url: string;
  model_identifier: string;
  api_key?: string | null;
}

export interface ModelConnectionTestResult {
  success: boolean;
  status: string;
  message: string;
  latency_ms?: number;
  supports_chat: boolean;
  supports_json: boolean;
  details?: Record<string, any>;
}

export async function listModelConnections(role?: string): Promise<ModelConnection[]> {
  const url = role ? `${API_BASE_URL}/models/connections?role=${encodeURIComponent(role)}` : `${API_BASE_URL}/models/connections`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to list model connections: ${res.statusText}`);
  return res.json();
}

export async function createModelConnection(data: Partial<ModelConnection>): Promise<ModelConnection> {
  const res = await fetch(`${API_BASE_URL}/models/connections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to register model connection: ${res.statusText}`);
  return res.json();
}

export async function testModelConnection(data: ModelConnectionTestRequest, signal?: AbortSignal): Promise<ModelConnectionTestResult> {
  const res = await fetch(`${API_BASE_URL}/models/connections/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    signal,
  });
  if (!res.ok) throw new Error(`Failed to test model endpoint: ${res.statusText}`);
  return res.json();
}

export async function updateModelConnection(connId: string, data: Partial<ModelConnection>): Promise<ModelConnection> {
  const res = await fetch(`${API_BASE_URL}/models/connections/${encodeURIComponent(connId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to update model connection: ${res.statusText}`);
  return res.json();
}

export async function getAgentModelBindings(agentId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/models/agent-bindings/${encodeURIComponent(agentId)}`);
  if (!res.ok) throw new Error(`Failed to get agent model bindings: ${res.statusText}`);
  return res.json();
}

export async function updateAgentModelBindings(agentId: string, payload: any): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/models/agent-bindings/${encodeURIComponent(agentId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to save agent model bindings: ${res.statusText}`);
  return res.json();
}

export async function setActiveModelConnection(connId: string): Promise<ModelConnection> {
  const res = await fetch(`${API_BASE_URL}/models/connections/${encodeURIComponent(connId)}/set-active`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to activate model connection: ${res.statusText}`);
  return res.json();
}

export async function deleteModelConnection(connId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/models/connections/${encodeURIComponent(connId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete model connection: ${res.statusText}`);
  return res.json();
}

// ── Training Dataset Builder Interfaces & API Methods ───────────────────────

export interface SFTMessage {
  role: string;
  content: string;
  name?: string;
  tool_calls?: Record<string, any>[];
}

export interface SFTExample {
  id: string;
  agent_id: string;
  scenario_id: string;
  scenario_title?: string;
  category: string;
  messages: SFTMessage[];
  created_at: string;
}

export interface PreferencePair {
  id: string;
  agent_id: string;
  scenario_id: string;
  prompt: string;
  chosen: string;
  rejected: string;
  reason: string;
  category: string;
  margin: number;
  created_at: string;
}

export interface FailureRecoveryExample {
  id: string;
  agent_id: string;
  scenario_id: string;
  error_state: string;
  attempted_action: string;
  corrected_action: string;
  recovery_strategy: string;
  created_at: string;
}

export interface TrainingDataset {
  id: string;
  agent_id: string;
  agent_name?: string;
  name: string;
  description?: string;
  dataset_type: 'SFT' | 'DPO_PREFERENCE' | 'FAILURE_RECOVERY' | 'HYBRID';
  format: string;
  example_count: number;
  sft_examples: SFTExample[];
  preference_pairs: PreferencePair[];
  recovery_examples: FailureRecoveryExample[];
  source_scenarios: string[];
  source_execution_runs: string[];
  export_ready: boolean;
  created_at: string;
  updated_at: string;
}

export async function listTrainingDatasets(agentId?: string): Promise<TrainingDataset[]> {
  const url = agentId ? `${API_BASE_URL}/training/datasets?agent_id=${encodeURIComponent(agentId)}` : `${API_BASE_URL}/training/datasets`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to list training datasets: ${res.statusText}`);
  return res.json();
}

export async function getTrainingDataset(datasetId: string): Promise<TrainingDataset> {
  const res = await fetch(`${API_BASE_URL}/training/datasets/${encodeURIComponent(datasetId)}`);
  if (!res.ok) throw new Error(`Failed to fetch dataset: ${res.statusText}`);
  return res.json();
}

export async function generateTrainingDataset(data: {
  agent_id: string;
  dataset_name: string;
  dataset_type?: string;
  evaluation_run_ids?: string[];
}): Promise<TrainingDataset> {
  const res = await fetch(`${API_BASE_URL}/training/datasets/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to generate training dataset: ${res.statusText}`);
  return res.json();
}

export function getExportDatasetUrl(datasetId: string, formatType: string = 'ALL'): string {
  return `${API_BASE_URL}/training/datasets/${encodeURIComponent(datasetId)}/export?format_type=${encodeURIComponent(formatType)}`;
}

export function getExportTrainingPackageUrl(datasetId: string): string {
  return `${API_BASE_URL}/training/datasets/${encodeURIComponent(datasetId)}/package`;
}

// ── Training Jobs, Hardware Preflight & Model Versioning ────────────────────

export interface HardwarePreflight {
  gpu_name: string;
  vram_mb: number;
  cuda_available: boolean;
  cuda_version: string;
  device_count: number;
  feasibility: 'CAN_TRAIN' | 'CAN_TRAIN_WITH_QLORA' | 'MAY_TRAIN_WITH_OFFLOAD' | 'INSUFFICIENT_VRAM';
  recommended_method: string;
  recommended_batch_size: number;
  recommended_gradient_accumulation_steps: number;
  recommended_max_seq_length: number;
  estimated_memory_usage_mb: number;
  notes: string;
}

export interface TrainingLossStep {
  step: number;
  epoch: number;
  train_loss: number;
  val_loss?: number | null;
  learning_rate: number;
  timestamp: string;
}

export interface TrainingCheckpoint {
  checkpoint_id: string;
  step: number;
  epoch: number;
  val_loss: number;
  artifact_path: string;
  is_best: boolean;
  created_at: string;
}

export interface ModelBenchmarkDelta {
  base_model_score: number;
  trained_adapter_score: number;
  score_delta: number;
  safety_delta: number;
  correctness_delta: number;
  robustness_delta: number;
  tool_discipline_delta: number;
  fixed_failures: number;
  regressions_detected: number;
  recommendation: 'RECOMMENDED_FOR_PROMOTION' | 'REVIEW_REQUIRED' | 'REJECTED';
}

export interface TrainingJob {
  id: string;
  agent_id: string;
  agent_name: string;
  model_connection_id: string;
  model_name: string;
  dataset_id: string;
  dataset_name: string;
  training_method: string;
  learning_rate: number;
  epochs: number;
  lora_r: number;
  lora_alpha: number;
  batch_size: number;
  gradient_accumulation_steps: number;
  status: 'CREATED' | 'PREFLIGHT' | 'STAGING_DATA' | 'TRAINING' | 'VALIDATING' | 'REGISTERING' | 'BENCHMARKING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  current_step_description: string;
  current_epoch: number;
  total_epochs: number;
  current_step: number;
  total_steps: number;
  progress_percentage: number;
  hardware_preflight: HardwarePreflight;
  loss_history: TrainingLossStep[];
  checkpoints: TrainingCheckpoint[];
  best_loss?: number | null;
  resulting_model_version_id?: string | null;
  benchmark_comparison?: ModelBenchmarkDelta | null;
  is_promoted: boolean;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ModelVersionRecord {
  id: string;
  agent_id: string;
  model_name: string;
  version_label: string;
  base_model: string;
  parent_version_id?: string | null;
  adapter_type: string;
  training_job_id?: string | null;
  dataset_id?: string | null;
  adapter_path?: string | null;
  is_active: boolean;
  benchmark_score: number;
  created_at: string;
}

export async function fetchHardwarePreflight(modelName: string = 'Qwen2.5-Coder-7B'): Promise<HardwarePreflight> {
  const res = await fetch(`${API_BASE_URL}/training/hardware-preflight?model_name=${encodeURIComponent(modelName)}`);
  if (!res.ok) throw new Error(`Failed to fetch hardware preflight: ${res.statusText}`);
  return res.json();
}

export async function startTrainingJob(data: {
  agent_id: string;
  model_connection_id: string;
  dataset_id: string;
  training_method?: string;
  epochs?: number;
  learning_rate?: number;
  lora_r?: number;
}): Promise<TrainingJob> {
  const res = await fetch(`${API_BASE_URL}/training/jobs/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to start training job: ${res.statusText}`);
  return res.json();
}

export async function listTrainingJobs(agentId?: string): Promise<TrainingJob[]> {
  const url = agentId ? `${API_BASE_URL}/training/jobs?agent_id=${encodeURIComponent(agentId)}` : `${API_BASE_URL}/training/jobs`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to list training jobs: ${res.statusText}`);
  return res.json();
}

export async function fetchTrainingJobDetails(jobId: string): Promise<TrainingJob> {
  const res = await fetch(`${API_BASE_URL}/training/jobs/${encodeURIComponent(jobId)}`);
  if (!res.ok) throw new Error(`Failed to fetch training job: ${res.statusText}`);
  return res.json();
}

export async function promoteModelVersion(jobId: string): Promise<ModelVersionRecord> {
  const res = await fetch(`${API_BASE_URL}/training/jobs/${encodeURIComponent(jobId)}/promote`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to promote model version: ${res.statusText}`);
  return res.json();
}

export async function listModelVersionRecords(agentId?: string): Promise<ModelVersionRecord[]> {
  const url = agentId ? `${API_BASE_URL}/training/models/versions?agent_id=${encodeURIComponent(agentId)}` : `${API_BASE_URL}/training/models/versions`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to list model versions: ${res.statusText}`);
  return res.json();
}

// ── Agent Pipeline Stage Status & Prerequisite Tracker ──────────────────────

export interface StageStepStatus {
  stage_id: string;
  stage_number: number;
  name: string;
  status: 'COMPLETED' | 'IN_PROGRESS' | 'READY_TO_START' | 'BLOCKED' | 'OPTIONAL_AVAILABLE';
  is_completed: boolean;
  is_blocked: boolean;
  blocker_reason?: string | null;
  next_action_route: string;
  next_action_label: string;
  metrics_summary?: string | null;
}

export interface AgentPipelineStageStatus {
  agent_id: string;
  agent_name: string;
  current_version: string;
  total_scenarios_count: number;
  executed_sessions_count: number;
  evaluated_verdicts_count: number;
  total_failures_count: number;
  critical_failures_count: number;
  latest_scorecard_score?: number | null;
  training_datasets_count: number;
  training_jobs_count: number;
  intake_completed: boolean;
  scenarios_generated: boolean;
  sandbox_ready: boolean;
  execution_completed: boolean;
  evaluation_completed: boolean;
  diagnosis_completed: boolean;
  ready_for_code_repair: boolean;
  ready_for_model_training: boolean;
  stages: StageStepStatus[];
  overall_pipeline_progress: number;
  recommended_next_stage: string;
  updated_at: string;
}

export async function fetchAgentPipelineStageStatus(agentId: string): Promise<AgentPipelineStageStatus> {
  const res = await fetch(`${API_BASE_URL}/pipeline/agents/${encodeURIComponent(agentId)}/status`);
  if (!res.ok) throw new Error(`Failed to fetch pipeline stage status: ${res.statusText}`);
  return res.json();
}

// ── Agent Tester & Parallel Stage Judge Subsystem ───────────────────────────

export interface StageAuditRequest {
  agent_id: string;
  stage_name: string;
  input_data?: Record<string, any>;
  result_data?: Record<string, any>;
  session_id?: string;
  requested_model?: string;
  custom_criteria?: string[];
}

export interface StageAuditVerdict {
  id: string;
  agent_id: string;
  stage_name: string;
  tester_session_id: string;
  model_used: string;
  provider_used: string;
  status: 'PASS' | 'WARNING' | 'DEFECT';
  score: number;
  fidelity_score: number;
  summary: string;
  input_summary: string;
  output_summary: string;
  strengths: string[];
  findings_and_discrepancies: string[];
  hallucination_detected: boolean;
  recommendations: string[];
  latency_ms: number;
  created_at: string;
}

export interface AgentAuditItem {
  agent_id: string;
  agent_name: string;
  status: 'PASS' | 'WARNING' | 'DEFECT';
  score: number;
  input_summary: string;
  output_summary: string;
  strengths: string[];
  discrepancies: string[];
  recommendations: string[];
  latency_ms?: number;
}

export interface TrainingRecord {
  stage: string;
  agent_id?: string;
  system_prompt: string;
  user_input: string;
  ideal_response: string;
  rejected_response?: string;
  reasoning_critique?: string;
}

export interface MultiAgentAuditRequest {
  agent_ids: string[];
  stage_name: string;
  requested_model?: string;
  custom_criteria?: string[];
}

export interface MultiAgentAuditVerdict {
  id: string;
  stage_name: string;
  agent_count: number;
  overall_status: 'PASS' | 'WARNING' | 'DEFECT';
  overall_score: number;
  overall_improvement_needed: string;
  system_prompt_recommendations: string[];
  code_remediation_recommendations: string[];
  agent_results: AgentAuditItem[];
  training_dataset: TrainingRecord[];
  local_fallback_model: string;
  tester_fallback_model: string;
  latency_ms: number;
  created_at: string;
}

export interface StageTesterHealth {
  active_cloud_keys: number;
  configured_model: string;
  local_model_endpoint: string;
  local_model_name: string;
  local_model_connected: boolean;
  local_model_status: string;
  available_sessions_count: number;
  stage_fallback_models?: Record<string, string>;
  tester_fallback_model?: string;
  status: 'healthy' | 'degraded' | 'offline';
}

export async function fetchStageTesterHealth(): Promise<StageTesterHealth> {
  const res = await fetch(`${API_BASE_URL}/agent-testers/health`);
  if (!res.ok) throw new Error(`Failed to fetch tester health: ${res.statusText}`);
  return res.json();
}

export async function runStageAudit(req: StageAuditRequest): Promise<StageAuditVerdict> {
  const res = await fetch(`${API_BASE_URL}/agent-testers/audit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Failed to execute stage audit: ${res.statusText}`);
  return res.json();
}

export async function runMultiAgentAudit(req: MultiAgentAuditRequest): Promise<MultiAgentAuditVerdict> {
  const res = await fetch(`${API_BASE_URL}/agent-testers/audit-batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Failed to execute multi-agent audit: ${res.statusText}`);
  return res.json();
}

export async function listStageAudits(agentId: string, stage?: string): Promise<StageAuditVerdict[]> {
  const url = stage
    ? `${API_BASE_URL}/agent-testers/audits/${encodeURIComponent(agentId)}?stage=${encodeURIComponent(stage)}`
    : `${API_BASE_URL}/agent-testers/audits/${encodeURIComponent(agentId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to list stage audits: ${res.statusText}`);
  return res.json();
}


// ── Zero-Friction Unified Requirement Resolution ────────────────────────────

export interface ExecutionRequirement {
  id: string;
  agent_id: string;
  type: string;
  name: string;
  detected_from: string;
  required: boolean;
  optional: boolean;
  default_available: boolean;
  platform_provider?: string;
  user_value_available: boolean;
  sandbox_adapter_available: boolean;
  resolved_value?: string;
  resolution_method: string;
  fidelity: 'FAITHFUL' | 'SIMULATED' | 'MODEL_SUBSTITUTED' | 'MOCKED';
  blocking: boolean;
  status: 'RESOLVED_PLATFORM' | 'RESOLVED_USER' | 'RESOLVED_SANDBOX' | 'OPTIONAL' | 'NEEDS_USER_INPUT' | 'BLOCKED';
  description: string;
  action_label?: string;
}

export interface AgentRequirementsReport {
  agent_id: string;
  agent_name: string;
  overall_status: 'READY' | 'NEEDS_INPUT' | 'BLOCKED';
  needs_user_input_count: number;
  total_requirements_count: number;
  ai_models: ExecutionRequirement[];
  external_services: ExecutionRequirement[];
  environment: ExecutionRequirement[];
  active_fidelity: string;
  generated_at: string;
}

export async function fetchAgentRequirementsReport(agentId: string): Promise<AgentRequirementsReport> {
  const res = await fetch(`${API_BASE_URL}/dependencies/requirements/${encodeURIComponent(agentId)}`);
  if (!res.ok) throw new Error(`Failed to fetch requirement resolution report: ${res.statusText}`);
  return res.json();
}

// =========================================================================
// Platform-AI Meta-Evaluation & Quality Lab Interfaces
// =========================================================================
export interface StageModelBinding {
  id: string;
  stage: 'INTAKE_ANALYST' | 'SCENARIO_PLANNER' | 'EXECUTION_OBSERVER' | 'IMPROVEMENT_ANALYST' | 'META_EVALUATOR';
  stage_name: string;
  primary_connection_id: string;
  fallback_connection_id: string;
  active_connection_id: string;
  fallback_enabled: boolean;
  primary_model: string;
  fallback_model: string;
  adapter_reference?: string;
  health_status: string;
  updated_at: string;
}

export interface StagePerformanceReport {
  stage: 'INTAKE_ANALYST' | 'SCENARIO_PLANNER' | 'EXECUTION_OBSERVER' | 'IMPROVEMENT_ANALYST';
  stage_name: string;
  model_connection_id: string;
  model_version_id: string;
  agents_tested: number;
  cases_evaluated: number;
  correct_count: number;
  missed_count: number;
  false_positive_count: number;
  accuracy_pct: number;
  precision_pct: number;
  recall_pct: number;
  coverage_pct: number;
  quality_score: number;
  failure_categories: Array<{
    agent?: string;
    category?: string;
    type?: string;
    source?: string;
    impact?: string;
    scenario?: string;
    trajectory?: string;
    reason?: string;
  }>;
  system_prompt_improvements: string[];
  code_remediation_rules: string[];
  training_candidates_count: number;
  evidence_references: string[];
  latency_ms: number;
}

export interface OverallPlatformPerformance {
  id: string;
  evaluated_agent_ids: string[];
  evaluated_agents_count: number;
  overall_score: number;
  overall_status: 'EXCELLENT' | 'OPTIMAL' | 'DEFECT' | 'DEGRADED';
  stage_reports: Record<string, StagePerformanceReport>;
  meta_judge_model: string;
  meta_judge_verdict_summary: string;
  evaluated_at: string;
}

export interface StageTrainingExample {
  id: string;
  stage: string;
  agent_id: string;
  agent_name: string;
  split: 'TRAIN' | 'VALIDATION' | 'HELD_OUT';
  source_reference: string;
  system_prompt: string;
  user_input: string;
  model_output: string;
  ground_truth: string;
  ideal_response: string;
  rejected_response: string;
  reasoning_critique: string;
  failure_category: string;
  approval_status: string;
  created_at: string;
}

export interface StageDatasetExport {
  stage: string;
  total_examples: number;
  train_count: number;
  validation_count: number;
  held_out_count: number;
  target_local_model: string;
  examples: StageTrainingExample[];
}

export interface ModelBenchmarkComparison {
  stage: string;
  benchmark_id: string;
  held_out_sample_count: number;
  model_v1_version: string;
  model_v1_accuracy: number;
  model_v1_quality_score: number;
  model_v2_version: string;
  model_v2_accuracy: number;
  model_v2_quality_score: number;
  delta_accuracy: number;
  improved: boolean;
  recommendation: 'PROMOTE_V2' | 'REJECT_V2' | 'RETRAIN_MORE_DATA';
  comparison_timestamp: string;
}

export async function fetchPlatformModelBindings(): Promise<StageModelBinding[]> {
  const res = await fetch(`${API_BASE_URL}/platform-ai/model-bindings`);
  if (!res.ok) throw new Error(`Failed to fetch model bindings: ${res.statusText}`);
  return res.json();
}

export async function runPlatformMetaEvaluation(agentIds: string[]): Promise<OverallPlatformPerformance> {
  const res = await fetch(`${API_BASE_URL}/platform-ai/performance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_ids: agentIds })
  });
  if (!res.ok) throw new Error(`Failed to run platform meta-evaluation: ${res.statusText}`);
  return res.json();
}

export async function fetchPlatformStageDataset(stage: string, agentIds?: string[]): Promise<StageDatasetExport> {
  const params = agentIds && agentIds.length > 0 ? `?agent_ids=${encodeURIComponent(agentIds.join(','))}` : '';
  const res = await fetch(`${API_BASE_URL}/platform-ai/dataset/${encodeURIComponent(stage)}${params}`);
  if (!res.ok) throw new Error(`Failed to export stage dataset: ${res.statusText}`);
  return res.json();
}

export async function compareModelBenchmarks(
  stage: string,
  modelV1: string,
  modelV2: string
): Promise<ModelBenchmarkComparison> {
  const res = await fetch(`${API_BASE_URL}/platform-ai/benchmark-compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stage, model_v1: modelV1, model_v2: modelV2 })
  });
  if (!res.ok) throw new Error(`Failed to benchmark models: ${res.statusText}`);
  return res.json();
}

export interface TelemetrySubmissionPayload {
  agent_id: string;
  evaluation_job_id?: string;
  note?: string;
  include_traces?: boolean;
  include_scorecard?: boolean;
}

export async function submitTelemetryToAdmin(payload: TelemetrySubmissionPayload): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/telemetry/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Failed to submit telemetry: ${res.statusText}`);
  return res.json();
}

export async function fetchAdminTelemetrySubmissions(): Promise<any[]> {
  const res = await fetch(`${API_BASE_URL}/telemetry/admin/submissions`);
  if (!res.ok) throw new Error(`Failed to fetch admin telemetry: ${res.statusText}`);
  return res.json();
}

export async function approveTelemetryForTraining(submissionId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/telemetry/admin/submissions/${submissionId}/approve`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`Failed to approve telemetry: ${res.statusText}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Improve Action Layer API Interfaces & Helper Functions
// ---------------------------------------------------------------------------

export interface ImproveSummary {
  status: 'HAS_FAILURES' | 'NO_FAILURES_DETECTED' | 'NO_EVALUATION_AVAILABLE' | 'PARTIAL_EVALUATION';
  message: string;
  agent_id: string;
  agent_name: string;
  evaluation_run_id: string;
  total_failures: number;
  critical_failures: number;
  repairable_issues: number;
  evaluation_fidelity: number;
  scenarios_evaluated: number;
  passed: number;
  failed: number;
  inconclusive: number;
  not_evaluable: number;
}

export interface RepairProposal {
  agent_id: string;
  old_version: string;
  new_version: string;
  affected_file: string;
  reason: string;
  source_failure_ids: string[];
  original_code: string;
  repaired_code: string;
  patch_diff: string;
}

export interface RegressionResult {
  status: 'PASS' | 'FAIL';
  message: string;
  agent_id: string;
  baseline_version: string;
  repaired_version: string;
  scenarios_tested: number;
  fixed_failures: number;
  new_regressions: number;
  metrics_delta: {
    safety: { before: number; after: number };
    correctness: { before: number; after: number };
    tool_discipline: { before: number; after: number };
    critical_failures: { before: number; after: number };
  };
  scenario_comparisons: Array<{
    scenario_id: string;
    before_status: string;
    after_status: string;
    delta: string;
  }>;
}

export async function fetchImproveSummary(agentId: string, runId?: string): Promise<ImproveSummary> {
  const params = new URLSearchParams({ agent_id: agentId });
  if (runId) params.append('evaluation_run_id', runId);
  const res = await fetch(`${API_BASE_URL}/improve/summary?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch improve summary: ${res.statusText}`);
  return res.json();
}

export async function proposeImproveRepair(agentId: string, runId?: string, findingId?: string): Promise<RepairProposal> {
  const res = await fetch(`${API_BASE_URL}/improve/propose-repair`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id: agentId, evaluation_run_id: runId, finding_id: findingId })
  });
  if (!res.ok) throw new Error(`Failed to generate repair proposal: ${res.statusText}`);
  return res.json();
}

export async function applyImproveRepair(
  agentId: string,
  newVersionLabel: string,
  patchDiff: string,
  reason: string,
  sourceFailureIds: string[],
  repairedSourceFiles: Record<string, string>
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/improve/apply-repair`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      new_version_label: newVersionLabel,
      patch_diff: patchDiff,
      repair_reason: reason,
      source_failure_ids: sourceFailureIds,
      repaired_source_files: repairedSourceFiles
    })
  });
  if (!res.ok) throw new Error(`Failed to apply repair: ${res.statusText}`);
  return res.json();
}

export async function runImproveRegression(agentId: string, baselineVer: string, repairedVer: string, runId?: string): Promise<RegressionResult> {
  const res = await fetch(`${API_BASE_URL}/improve/run-regression`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      baseline_version: baselineVer,
      repaired_version: repairedVer,
      evaluation_run_id: runId
    })
  });
  if (!res.ok) throw new Error(`Failed to run regression: ${res.statusText}`);
  return res.json();
}

export async function generateImproveTrainingDataset(agentId: string, datasetName: string, runId?: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/improve/training-dataset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      dataset_name: datasetName,
      dataset_type: 'HYBRID',
      evaluation_run_id: runId
    })
  });
  if (!res.ok) throw new Error(`Failed to generate dataset: ${res.statusText}`);
  return res.json();
}

export async function getSetupReadiness(agentId: string): Promise<SetupReadinessRecord> {
  const res = await fetch(`${API_BASE_URL}/dependencies/agents/${agentId}/setup-readiness`);
  if (!res.ok) throw new Error(`Failed to get setup readiness: ${res.statusText}`);
  return res.json();
}

export async function runAutomaticSetup(agentId: string): Promise<SetupReadinessRecord> {
  const res = await fetch(`${API_BASE_URL}/dependencies/agents/${agentId}/run-setup`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`Failed to run automatic setup: ${res.statusText}`);
  return res.json();
}



