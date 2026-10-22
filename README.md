# TrustReply

**Answer security questionnaires in minutes, with evidence for every answer.**

Startups lose deals when they can't quickly complete a customer's security questionnaire (SIG Lite, CAIQ, custom spreadsheets, SOC 2 or ISO 27001 requests). TrustReply reads your real security policies, drafts an answer for every question, cites the exact policy text behind each answer, and openly flags the questions you cannot honestly answer yet.

> Status: early development (Phase 0). Not ready for production use.

## Principles

1. **Every answer is cited.** No source, no answer.
2. **Gaps are flagged, never invented.** If your policies don't cover a control, TrustReply says so.
3. **Humans approve.** The tool drafts; a person reviews before anything is sent.
4. **Your data stays yours.** Documents are processed locally by default, and nothing is stored beyond what you configure.

## Planned features (v0.1)

- Ingest policies (PDF, DOCX, Markdown, TXT)
- Parse questionnaires (XLSX, CSV)
- Draft cited answers with a confidence level
- Export a filled spreadsheet plus a gap report
- Use it from a command line or a web interface

## Quick start

Coming in Phase 2. See [docs/ROADMAP.md](docs/ROADMAP.md) for the plan.

## Documentation

- [Roadmap](docs/ROADMAP.md)
- [GitHub workflow guide](docs/GITHUB_WORKFLOW.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT
