# Copilot Chat Instructions (Repo Rules)

## Safety / Confirmation
- Any action that changes git state (commit, push, branch, rebase, amend) MUST be explicitly confirmed by the user first.
- Never run `git push` unless the user explicitly says "push".

## Quality Gates (Required)
- After ANY code change (including refactor), MUST run:
  1) lint
  2) unit tests
- If lint or tests fail, fix and re-run until green.
- Summarize results (commands run + pass/fail) before proposing next steps.

## Git workflow
- You MAY create a commit only if the user explicitly requests it.
- Default behavior: make local changes only, do not commit, do not push.

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