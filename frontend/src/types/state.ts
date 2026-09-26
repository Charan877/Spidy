export interface Task {
  id: string;
  title: string;
  phase: string;
  status: 'QUEUED' | 'READY' | 'RUNNING' | 'BLOCKED' | 'SUCCESS' | 'FAILED' | 'SKIPPED' | 'CANCELLED';
  agent_assigned: string;
  file_path?: string | null;
  dependencies: string[];
  blocked_reason?: string | null;
  result?: string | null;
}

export interface ActivityLog {
  timestamp: string;
  message: string;
  level: 'ok' | 'run' | 'bad' | 'dim';
}

export interface VerificationGates {
  build: boolean;
  process: boolean;
  port: boolean;
  server: boolean;
  http: boolean;
  application: boolean;
}

export interface RuntimeTarget {
  type: 'web' | 'api' | 'docs' | 'service';
  name: string;
  url: string;
  port: number;
  pid?: number | null;
  status: string;
  framework?: string;
}

export interface ProjectStateSnapshot {
  project_name: string;
  goal: string;
  detected_language: string;
  selected_language: string;
  effective_language: string;
  architecture_summary: string;
  tech_stack: string[];
  clarifying_questions: Array<{ question: string; [key: string]: any }>;
  clarification_answers: Record<string, string>;
  user_approved: boolean;
  current_phase: string;
  project_state: string;
  active_agent: string;
  active_agent_status: string;
  current_task_description: string;
  current_file_target: string;
  tasks: Task[];
  tasks_completed: number;
  tasks_total: number;
  progress_percent: number;
  activity_feed: ActivityLog[];
  errors: string[];
  is_running: boolean;
  project_generation_status: string;
  is_project_generated: boolean;
  recovery_attempts: number;
  project_type: string;
  project_id?: string;
  build_id?: string;
  conversation_id?: string;
  current_classification?: string;
  fullstack_contract?: Record<string, any>;
  known_issues?: string[];
  reviewer_verdict?: string | null;
  files_affected?: string[];
  has_failed_required_tasks?: boolean;
  runtime_type?: 'api' | 'web' | 'fullstack' | 'cli' | 'library' | string;
  runtime_targets?: RuntimeTarget[];
  is_web_project: boolean;
  runtime_status: string;
  runtime_command: string;
  runtime_pid: number | null;
  runtime_port: number | null;
  runtime_url: string | null;
  runtime_logs: string;
  is_app_verified: boolean;
  verification_gates: VerificationGates;
  project_success: boolean;
  failure_reason: string | null;
  failure_classification: string | null;
  elapsed_seconds: number;
  formatted_elapsed: string;
  estimated_duration_str: string;
  estimated_remaining_str: string;
  estimated_complexity: string;
  estimated_confidence: string;
  actual_duration_str: string | null;
  files_count: number;
  files_list: string[];
}

export interface ChatMessage {
  message_id: string;
  project_id: string;
  build_id?: string | null;
  role: 'user' | 'assistant';
  content: string;
  classification?: string | null;
  timestamp: string;
}

export interface DbProject {
  project_id: string;
  name: string;
  description: string;
  workspace_path: string;
  detected_stack: string;
  status: string;
  created_at: string;
  updated_at: string;
  build_count?: number;
}

export interface DbBuild {
  build_id: string;
  project_id: string;
  requirement: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
  duration?: number | null;
  estimated_duration?: string | null;
  final_result?: string | null;
  failure_reason?: string | null;
  created_at: string;
}

export interface DbAgentRun {
  run_id: string;
  build_id: string;
  agent_name: string;
  task_id?: string | null;
  status: string;
  started_at: string;
  completed_at?: string | null;
  duration?: number | null;
  error_message?: string | null;
}

export interface DbActivity {
  activity_id: string;
  build_id: string;
  timestamp: string;
  event_type: string;
  agent?: string | null;
  message: string;
  status?: string | null;
}

export interface DbRuntimeSession {
  runtime_id: string;
  build_id: string;
  project_id: string;
  framework?: string | null;
  pid?: number | null;
  port?: number | null;
  url?: string | null;
  status: string;
  health_status?: string | null;
  started_at: string;
  stopped_at?: string | null;
}

export interface DbVerificationGate {
  verification_id: string;
  build_id: string;
  gate_name: string;
  status: string;
  message?: string | null;
  timestamp: string;
}

export interface DbDiagnostics {
  status: string;
  db_path: string;
  schema_version: number;
  target_version: number;
  counts: {
    projects: number;
    builds: number;
    agent_runs: number;
    activities: number;
    runtime_sessions: number;
    verification: number;
  };
}

export interface HistoryItem {
  project_id: string;
  project_name: string;
  goal: string;
  tech_stack: string;
  status: string;
  actual_duration_str: string;
  actual_duration_seconds: number;
  estimate_range: string;
  timestamp: string;
  build_id: string;
}

