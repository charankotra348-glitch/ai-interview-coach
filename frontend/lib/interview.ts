/** Pure helpers for the interview screen. No React, no fetch: easy to test. */
import type { Mode, Question, Session } from "@/lib/types";

export const MODE_NAMES: Record<Mode, string> = {
  behavioral: "Behavioral",
  project: "Your projects",
  system_design: "System design",
};

export const DIFFICULTY_NAMES: Record<number, string> = { 1: "Warm-up", 2: "Standard", 3: "Stretch" };

export const MIN_ANSWER_CHARS = 20;
export const MAX_ANSWER_CHARS = 6000;

/** The question waiting for an answer, if any. */
export function pendingQuestion(session: Session): Question | null {
  return session.questions.find((q) => q.answer === null) ?? null;
}

export function answeredCount(session: Session): number {
  return session.questions.filter((q) => q.answer !== null).length;
}

/** What the screen should do next. */
export function stage(session: Session): "answer" | "ask" | "finished" {
  if (pendingQuestion(session)) return "answer";
  return session.status === "active" ? "ask" : "finished";
}

/**
 * Turns the backend's rationale into a sentence for the candidate:
 * "follow-up: Reflection scored 2/5" -> "Follow-up: Reflection scored 2/5 on your last answer."
 */
export function explainRationale(rationale: string | null): string | null {
  if (!rationale || rationale === "opening question") return null;
  const followUp = rationale.match(/^follow-up: (.+)$/);
  if (followUp) return `Follow-up: ${followUp[1]} on your last answer.`;
  const newTopic = rationale.match(/^new topic, [a-z-]+: (.+)$/);
  if (newTopic) return `New topic, ${newTopic[1]}.`;
  return null;
}

export function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

/** Seconds spent on a question, capped to what the API accepts. */
export function secondsSince(startMs: number, nowMs: number): number {
  return Math.min(3600, Math.max(0, Math.round((nowMs - startMs) / 1000)));
}