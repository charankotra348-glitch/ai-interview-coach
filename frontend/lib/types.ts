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