# Copilot Chat Instructions (Repo Rules)

## Safety / Confirmation
- Any action that changes git state (commit, push, branch, rebase, amend) MUST be explicitly confirmed by the user first.
- Never run `git push` unless the user explicitly says "push".
- **CRITICAL**: Even if the user says "commit", do NOT automatically push. Push requires explicit "push" command.

## Quality Gates (Required)
- After ANY code change (including refactor), MUST run the following checks **BEFORE** any git commit:

### Frontend Lint & Test
```bash
cd /path/to/buildflow && npm run lint:check
cd /path/to/buildflow && npm test
```
- Expected: 0 errors (warnings are acceptable)

### Backend Lint & Test
```bash
cd /path/to/buildflow/backend && ruff check .
cd /path/to/buildflow/backend && python3 -m pytest tests/ -v --tb=short
```
- Expected: "All checks passed!" for ruff, all tests passed for pytest

### Validation Flow
1. Run frontend lint (`npm run lint:check`) → must have 0 errors
2. Run frontend tests (`npm test`) → must pass
3. Run backend lint (`ruff check .`) → must pass
4. Run backend tests (`python3 -m pytest tests/`) → must pass
5. If any check fails, fix the issues and re-run until green
6. Summarize results (commands run + pass/fail) before proposing next steps

## Git workflow
- You MAY create a commit only if the user explicitly requests it.
- Default behavior: make local changes only, do not commit, do not push.
- **NEVER push automatically** - push requires explicit user confirmation with the word "push".

## Terminal Operation Rules
- Long-running processes (backend, frontend) MUST be executed only in the terminal named after the corresponding service.
- Test, lint, and validation commands MUST be executed only in the "test" terminal.
- Do NOT create loops that repeatedly start and stop servers in the same terminal.
- When a server restart is required, first check for existing processes or port usage, then restart the server only once.
- Whenever possible, use a smoke test script (start server → health check → stop server).

## Reporting
- Before finishing, provide a checklist:
  - [ ] lint passed
  - [ ] tests passed
  - [ ] no push performed