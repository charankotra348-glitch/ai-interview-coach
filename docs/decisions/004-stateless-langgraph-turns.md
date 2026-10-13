# 004: LangGraph runs one turn at a time; Postgres is the only source of truth

Status: Accepted (2026-10-13)

## Context

Step 6 makes the interview adaptive: after each answer, the system either asks one
follow-up on a weak criterion, moves to a new topic at a higher or lower difficulty,
or finishes. We use LangGraph to orchestrate this. LangGraph can also keep its own
state between steps (checkpointers) and pause a graph while it waits for a person
(interrupts).

Everything an interview needs is already stored in our own tables: questions, answers,
evaluations, difficulty, and why each question was asked.

## Decision

1. **One graph run per HTTP request.** The turn graph is `decide -> follow_up | new_question | end`.
   It runs when the client asks for the next question and finishes within that request.
2. **No checkpointer, no interrupts.** The service rebuilds the graph's input from Postgres
   on every turn, and the graph never touches the database. Waiting for an answer is just
   the time between two HTTP requests.
3. **Decisions are deterministic code** (`app/interview/policy.py`). The graph routes on
   them; the model only writes question text.
4. **A follow-up costs no extra model call.** It reuses the follow-up the grader already wrote.
   If that text is missing, too short, or repeats an earlier question, the interview moves on.

## Why

- A checkpointer would keep a second copy of interview state that could disagree with our
  tables, and we would need a way to reconcile the two. One source of truth avoids that.
- A stateless graph is easy to test without a database, and any server can handle any turn,
  which matters when several containers run on ECS.
- Rebuilding state is cheap: an interview has at most 10 questions.

## Measured costs

- Graph and policy overhead per turn, with model calls excluded: about 1 ms p50.
- Importing LangGraph adds about 0.5 s to server startup (app import went from about
  0.65 s to about 1.15 s). That is acceptable for a long-running server, though it
  would matter more for a per-request runtime such as Lambda.

## Consequences and limits

- Follow-up answers are graded on the full rubric even though they are short. Because of
  this, difficulty follows only the main answer, and the summary measures follow-ups only
  on the criterion they targeted (`follow_up_target_delta`).
- The thresholds (probe at 2/5 or below, harder at 8/10 or above, easier at 4/10 or below)
  are hypotheses. They are validated with the evaluation harness, per decision 003.
- The grader's follow-up is not checked for invented premises. Its prompt says to build only
  on what the answer says, which is weaker than a check in code.

## Revisit when

- A turn needs several model steps that must survive a crash partway through (for example,
  a voice pipeline). Then a checkpointer earns its place.
- LangGraph stops adding anything a plain function would not. The graph is three nodes
  over `decide()`, so removing it would be a small change.