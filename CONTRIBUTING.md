# Contributing to TrustReply

Thanks for helping. Please read [docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md) first.

## Quick rules

1. Open or pick an issue before starting work.
2. Branch from `main` using `feat/`, `fix/`, `docs/`, `chore/` or `test/` prefixes.
3. Use Conventional Commit messages.
4. Add or update tests for behavior changes.
5. Run `ruff check .`, `ruff format .` and `pytest` before pushing.
6. Open a pull request; it is squash-merged after review.

## Security

Never commit secrets or real customer documents. Report vulnerabilities privately; see `SECURITY.md` (coming in Phase 3).

## Principles for changes

- Every generated answer must keep a verifiable citation.
- When evidence is missing, the tool must say so rather than guess.
