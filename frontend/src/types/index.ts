/* ------------------------------------------------------------------ */
/*  FORGE — Shared TypeScript Interfaces                              */
/*  Matches backend SQLAlchemy models / Pydantic schemas               */
/* ------------------------------------------------------------------ */

export interface User {
  id: string
  email: string
  display_name: string
  avatar_url: string | null
  plan: 'free' | 'pro' | 'enterprise'
  onboarding_completed: boolean
  created_at: string
  updated_at: string
}

export interface Project {
  id: string
  user_id: string
  name: string
  description: string | null
  prompt: string | null
  framework: string | null
  status: 'draft' | 'building' | 'live' | 'error'
  sandbox_url: string | null
  preview_url: string | null
  cloud_services: string[]
  created_at: string
  updated_at: string
}

export interface PipelineRun {
  id: string
  project_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  current_stage: string | null
  current_stage_index: number
  total_stages: number
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  created_at: string
}

export interface Build {
  id: string
  project_id: string
  pipeline_run_id: string
  agent_name: string
  agent_index: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  output: string | null
  files_generated: string[]
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface Sandbox {
  id: string
  project_id: string
  url: string
  status: 'provisioning' | 'running' | 'stopped' | 'error'
  container_id: string | null
  port: number | null
  created_at: string
  updated_at: string
}

export interface EditorSession {
  id: string
  project_id: string
  user_id: string
  active_file: string | null
  open_files: string[]
  cursor_position: { line: number; column: number } | null
  preview_visible: boolean
  preview_device: 'desktop' | 'mobile'
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  project_id: string
  user_id: string | null
  role: 'user' | 'assistant' | 'system'
  content: string
  code_blocks: ChatCodeBlock[]
  created_at: string
}

export interface ChatCodeBlock {
  filename: string
  language: string
  code: string
  applied: boolean
}

export interface Idea {
  id: string
  session_id: string
  title: string
  tagline: string
  problem: string
  solution: string
  tech_stack: string[]
  uniqueness_score: number
  complexity_score: number
  market_size: string | null
  revenue_model: string | null
  saved: boolean
  created_at: string
}

export interface IdeaSession {
  id: string
  user_id: string
  mode: 'questionnaire' | 'direct'
  status: 'in_progress' | 'completed' | 'expired'
  answers: Record<string, string | string[]>
  ideas_count: number
  expires_at: string
  created_at: string
}

export interface Annotation {
  id: string
  project_id: string
  user_id: string
  snapshot_id: string | null
  x_pct: number
  y_pct: number
  css_selector: string | null
  comment: string
  resolved: boolean
  route: string | null
  created_at: string
}

export interface BuildSnapshot {
  id: string
  project_id: string
  pipeline_run_id: string
  agent_index: number
  image_url: string
  route: string
  created_at: string
}

export interface PreviewShare {
  id: string
  project_id: string
  user_id: string
  share_token: string
  expires_at: string
  created_at: string
}
