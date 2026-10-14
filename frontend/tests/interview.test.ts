import { describe, expect, it } from "vitest";
import { answeredCount, explainRationale, pendingQuestion, secondsSince, stage, wordCount } from "@/lib/interview";
import type { Question, Session } from "@/lib/types";

function question(position: number, answered: boolean): Question {
  return {
    id: `q${position}`, position, text: `Question ${position}`, difficulty: 2, is_follow_up: false,
    rationale: null, answer: answered ? "An answer that is long enough." : null, evaluation: null,
  };
}

function session(questions: Question[], status: Session["status"] = "active"): Session {
  return { id: "s1", mode: "behavioral", status, target_role: "Intern", max_questions: 3, questions };
}

describe("interview stage", () => {
  it("asks for the first question of a new interview", () => {
    expect(stage(session([]))).toBe("ask");
  });

  it("waits for an answer while a question is open", () => {
    const s = session([question(1, true), question(2, false)]);
    expect(stage(s)).toBe("answer");
    expect(pendingQuestion(s)?.id).toBe("q2");
    expect(answeredCount(s)).toBe(1);
  });

  it("asks for the next question once everything is answered", () => {
    expect(stage(session([question(1, true)]))).toBe("ask");
  });

  it("is finished when the backend says so", () => {
    expect(stage(session([question(1, true)], "completed"))).toBe("finished");
  });
});

describe("why a question was asked", () => {
  it("explains a follow-up", () => {
    expect(explainRationale("follow-up: Reflection scored 2/5"))
      .toBe("Follow-up: Reflection scored 2/5 on your last answer.");
  });

  it("explains a difficulty change", () => {
    expect(explainRationale("new topic, stretch: harder after a strong answer (9/10)"))
      .toBe("New topic, harder after a strong answer (9/10).");
  });

  it("says nothing for the opening question or unknown text", () => {
    expect(explainRationale("opening question")).toBeNull();
    expect(explainRationale(null)).toBeNull();
    expect(explainRationale("something else")).toBeNull();
  });
});

describe("answer helpers", () => {
  it("counts words, ignoring extra spaces", () => {
    expect(wordCount("  I owned   the fix \n end to end ")).toBe(7);
    expect(wordCount("   ")).toBe(0);
  });

  it("caps the time spent to what the API accepts", () => {
    expect(secondsSince(0, 90_400)).toBe(90);
    expect(secondsSince(0, 5 * 3600 * 1000)).toBe(3600);
    expect(secondsSince(1000, 0)).toBe(0);
  });
});