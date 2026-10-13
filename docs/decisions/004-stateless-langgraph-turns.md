# 004: LangGraph runs one turn at a time; Postgres is the only source of truth

Status: Accepted (2026-10-13). Revised the same day: point 4, after the first real interview.

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
4. **Code picks what a follow-up asks about; the model only words it.** The policy chooses the
   weakest criterion, and a dedicated model call writes one question about exactly that
   criterion, built on the candidate's last question and answer. This costs one extra model
   call per follow-up.

### Revision: why follow-ups are no longer free

The first version reused the follow-up the grader writes while grading, which cost no extra
call. In the first real interview, the policy correctly chose Reflection (2/5), but the
grader's follow-up asked about DeepSORT settings, which is a Specificity question. The prompt
told the grader to aim at the weakest criterion, and it did not. That let the model decide
what to ask, against this project's rule, and it would have made `follow_up_target_delta`
measure a criterion the question never asked about. Correct targeting is worth one call.

## Why

- A checkpointer would keep a second copy of interview state that could disagree with our
  tables, and we would need a way to reconcile the two. One source of truth avoids that.
- A stateless graph is easy to test without a database, and any server can handle any turn,
  which matters when several containers run on ECS.
- Rebuilding state is cheap: an interview has at most 10 questions.

## Measured costs

Measured on a MacBook Air, warm (after the first run):

- Graph and policy overhead per turn, with model calls excluded: about 1 ms p50.
- App import (server startup): about 0.59 s, of which LangGraph is about 0.37 s.
- The first import after installing packages takes about 1.5 s, because Python compiles
  bytecode for the new packages. This happens once per install, or once per new container
  image if the bytecode isn't compiled at build time.

This is paid once when the server starts, never per request. It would matter for a runtime
that starts a fresh process per request (for example Lambda), not for a long-running
server on ECS.

## Consequences and limits

- Follow-up answers are graded on the full rubric even though they are short. Because of
  this, difficulty follows only the main answer, and the summary measures follow-ups only
  on the criterion they targeted (`follow_up_target_delta`).
- The thresholds (probe at 2/5 or below, harder at 8/10 or above, easier at 4/10 or below)
  are hypotheses. They are validated with the evaluation harness, per decision 003.
- Follow-ups are not checked in code for invented premises, or for whether they really ask
  about the target criterion. The prompt names only that criterion and says to build only on
  what the answer says. Checking this is a job for the evaluation harness (decision 003).
- The same first interview showed the grader scoring "the tracking worked a lot better" 4/5 on
  Impact. The outcome criteria (Impact, Results) now say that a vague outcome with no measure
  scores at most 2. Whether this anchor helps is measured in Step 10.

## Revisit when

- A turn needs several model steps that must survive a crash partway through (for example,
  a voice pipeline). Then a checkpointer earns its place.
- LangGraph stops adding anything a plain function would not. The graph is three nodes
  over `decide()`, so removing it would be a small change.