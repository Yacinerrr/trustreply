# TrustReply Roadmap

## Goal

A tool a startup founder can use on Monday: upload policies and a customer's security questionnaire, get back a filled spreadsheet where every answer cites its source and every gap is flagged.

## Target user

Founders and CTOs of small SaaS companies (especially in Africa and MENA) who sell to banks, fintechs and enterprises and face security reviews without a dedicated security team.

## Architecture

```
trustreply/
  core/        ingestion, chunking, retrieval, answer drafting (no web or CLI code)
  cli/         Typer command line, thin wrapper over core
  web/         FastAPI app, thin wrapper over core
tests/
docs/
```

One shared `core`; the CLI and web app only call it. This keeps logic testable and avoids duplicated behavior.

## Core pipeline

1. **Ingest** policy documents into text chunks with source and page metadata.
2. **Index** chunks for retrieval (start with BM25 keyword search, add embeddings later if evaluation shows it helps).
3. **Parse** the questionnaire into a list of questions and their cell locations.
4. **Retrieve** the most relevant chunks per question.
5. **Draft** an answer with an LLM, constrained to the retrieved text, returning: answer (Yes/No/Partial/N/A), explanation, citations, confidence.
6. **Verify** that each citation actually supports the answer; downgrade to "gap" if not.
7. **Export** filled spreadsheet plus gap report.

## Phases

### Phase 0: Foundation (this step)
- [ ] Repo created on GitHub with branch protection
- [ ] README, LICENSE, CONTRIBUTING, .gitignore, pyproject
- [ ] Branching workflow documented and practiced with one PR

### Phase 1: Core engine
- [ ] Document ingestion (PDF, DOCX, MD, TXT)
- [ ] Questionnaire parser (XLSX, CSV)
- [ ] Retrieval with BM25
- [ ] LLM answer drafting with structured output
- [ ] Citation verification and gap detection
- [ ] Unit tests with sample policies and a sample questionnaire

### Phase 2: Interfaces
- [ ] CLI: `trustreply fill --policies ./policies --questionnaire q.xlsx --out filled.xlsx`
- [ ] FastAPI app: upload, progress, review screen, download
- [ ] Human review step: approve or edit each answer before export

### Phase 3: Proof and release
- [ ] Evaluation set of questions with known-correct answers, measuring accuracy, citation validity and false-confidence rate
- [ ] GitHub Actions CI (lint, type check, tests)
- [ ] Dockerfile and one-command run
- [ ] v0.1.0 release with changelog
- [ ] Case study write-up with real numbers
- [ ] Short demo video

## Definition of done for v0.1.0

- A new user can go from clone to a filled questionnaire in under 10 minutes using the docs alone.
- Every answer has a verifiable citation or is marked as a gap.
- Evaluation results are published in the repo.
- CI is green on `main`.

## Risks

| Risk | Mitigation |
|---|---|
| Hallucinated answers | Constrain to retrieved text, verify citations, flag gaps |
| Sensitive documents sent to an LLM provider | Document this clearly, support redaction, make provider configurable |
| Questionnaire formats vary wildly | Start with one or two formats, add a column-mapping option |
| Scope creep | Anything outside the v0.1 list goes to a backlog issue |
