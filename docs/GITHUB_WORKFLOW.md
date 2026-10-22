# GitHub Workflow Guide

This is how we set up the repo and ship every change. Follow it from day one so the history looks professional.

## 1. One-time setup

### Create the account and repo
1. Create an account at github.com if you don't have one. Enable two-factor authentication (Settings, Password and authentication).
2. Click **New repository**.
   - Name: `trustreply`
   - Visibility: Public
   - Do **not** add a README, .gitignore or license (we already have them locally)
3. Copy the repo URL.

### Install and configure Git
```bash
git --version
git config --global user.name "Your Name"
git config --global user.email "your-github-email@example.com"
git config --global init.defaultBranch main
```

### Authenticate
Easiest: install GitHub CLI and run `gh auth login`. Alternative: set up an SSH key and add it in GitHub settings.

### Connect and push the first commit
```bash
cd trustreply
git init
git add .
git commit -m "chore: initial project scaffold"
git branch -M main
git remote add origin https://github.com/<your-username>/trustreply.git
git push -u origin main
```

### Protect `main`
In the repo go to **Settings, Branches, Add rule** for `main`:
- Require a pull request before merging
- Require status checks to pass (add once CI exists in Phase 3)
- Require conversation resolution before merging
- Do not allow force pushes

## 2. Branching model

Simple trunk-based flow:

- `main` is always working and releasable.
- Every change lives on a short-lived branch created from `main`.

Branch names:
| Prefix | Use |
|---|---|
| `feat/` | New feature, e.g. `feat/pdf-ingestion` |
| `fix/` | Bug fix |
| `docs/` | Documentation only |
| `chore/` | Tooling, config, dependencies |
| `test/` | Tests only |

## 3. Commit messages

Use Conventional Commits:
```
feat: add DOCX policy ingestion
fix: handle empty cells in questionnaire parser
docs: explain evaluation method
```
Keep commits small and focused; one idea per commit.

## 4. The daily loop

```bash
git switch main
git pull
git switch -c feat/pdf-ingestion

# ...write code and tests...

git add -A
git commit -m "feat: extract text and page numbers from PDFs"
git push -u origin feat/pdf-ingestion
```
Then open a pull request on GitHub (or `gh pr create --fill`).

## 5. Pull requests

Every PR should have:
- A clear title in Conventional Commit style
- What changed and why
- How you tested it
- Linked issue (`Closes #12`)

Review your own PR before merging: read the diff tab like a stranger would.

**Merge method:** use **Squash and merge** so `main` gets one clean commit per PR. Delete the branch after merging.

After merging:
```bash
git switch main
git pull
git branch -d feat/pdf-ingestion
```

## 6. Issues and project tracking

- Turn every roadmap checkbox into a GitHub Issue.
- Label them (`feature`, `bug`, `docs`, `good first issue`).
- Create a GitHub Project board with columns: Backlog, In progress, In review, Done.
- Group issues into milestones: `v0.1.0-phase-1`, `v0.1.0-phase-2`, and so on.

## 7. Releases

When Phase 3 is done:
```bash
git switch main && git pull
git tag -a v0.1.0 -m "First public release"
git push origin v0.1.0
```
Then create a **Release** on GitHub with notes: highlights, known limitations, upgrade steps.

Versioning follows Semantic Versioning: `MAJOR.MINOR.PATCH`.

## 8. Handling mistakes

| Situation | Fix |
|---|---|
| Committed to `main` by accident (not yet pushed) | `git switch -c feat/x` then `git switch main && git reset --hard origin/main` |
| Wrong commit message (not yet pushed) | `git commit --amend` |
| Need to undo a merged change | `git revert <commit>` |
| Merge conflict | Pull latest `main` into your branch, resolve the marked files, `git add`, `git commit` |
| Secret committed | Rotate the secret immediately, then remove it from history; assume it is compromised |

## 9. Never commit

API keys, `.env` files, real customer questionnaires, real company policies. This is a security project, so the repo must be an example of good hygiene.
