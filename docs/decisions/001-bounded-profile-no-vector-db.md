# 001: Bounded structured profiles, no vector database

Status: Accepted (2026-10-11, revised 2026-10-13)

## Context
Inputs are one resume (1-2 pages) and one job description. Both fit in a
single prompt. This project is separate from RAGForge.

## Decision
Parse documents into bounded Pydantic models (CandidateProfile, JobProfile)
with hard limits on list sizes and text lengths. Compute the skill gap in
deterministic code, not with the model. No embeddings or vector database.

## Enforced by
- Validators truncate oversized lists and text instead of rejecting them
- Uploads are limited to 5 MB, 10 pages and 20,000 characters of text
- Extracted skills must appear in the source text (grounding check);
  ungrounded items are dropped and counted
- Uploaded files are processed in memory and never stored. Only the bounded
  profile is saved (no name, contact details or links). Re-extraction after
  a prompt improvement requires the user to re-upload.

## Revision (2026-10-13)
The original plan stored raw files in S3 with a deletion rule. Dropped:
the app never needs the raw file after extraction, and data that is never
stored cannot leak.

## Revisit if
We need search across a large corpus, such as thousands of past questions.
