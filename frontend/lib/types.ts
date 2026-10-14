/** Shapes returned by the FastAPI backend, as the frontend uses them. */

export type Me = { id: string; email: string };

export type Project = { name: string; summary: string; technologies: string[] };

export type CandidateProfile = {
  headline: string;
  skills: string[];
  projects: Project[];
  roles: { title: string; organization: string; summary: string }[];
};

export type JobProfile = {
  title: string;
  company?: string;
  required_skills: string[];
  nice_to_have_skills: string[];
  responsibilities?: string[];
};

export type Stored<T> = {
  id: string;
  created_at: string;
  profile: T;
  source_format: string;
  truncated: boolean;
  dropped_count: number;
};

export type Gap = {
  matched: { requirement: string; via: string }[];
  missing_required: string[];
  missing_nice_to_have: string[];
  coverage: number | null;
};

export type Mode = "behavioral" | "project" | "system_design";

export type SessionItem = {
  id: string;
  mode: Mode;
  status: "active" | "completed" | "abandoned";
  target_role: string;
  max_questions: number;
  answered: number;
  created_at: string;
};


export type RubricItem = { name: string; score: number; evidence: string; note: string };

export type Evaluation = {
  overall: number;
  rubric: RubricItem[];
  strengths: string[];
  improvements: string[];
  feedback_source: "model" | "derived";
  follow_up_question: string;
  ungrounded_evidence: number;
};

export type Question = {
  id: string;
  position: number;
  text: string;
  difficulty: number;
  is_follow_up: boolean;
  rationale: string | null;
  answer: string | null;
  evaluation: Evaluation | null;
};

export type Session = {
  id: string;
  mode: Mode;
  status: "active" | "completed" | "abandoned";
  target_role: string;
  max_questions: number;
  questions: Question[];
};

export type Summary = {
  answered: number;
  average_overall: number | null;
  criteria_averages: Record<string, number>;
  follow_ups: number;
  follow_up_target_delta: number | null;
  difficulty_path: number[];
  llm_calls: number;
  failed_llm_calls: number;
  estimated_cost_usd: string;
  calls_without_cost: number;
  llm_latency_ms: number;
};