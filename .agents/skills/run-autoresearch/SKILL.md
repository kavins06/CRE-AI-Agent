---
name: run-autoresearch
description: Run one autoresearch session that improves the analyst brain for one deliverable kind, following program.md exactly.
---
# Run autoresearch

1. Read `program.md` and `docs/LEARNING.md`. They are the charter, and you must not edit them.
2. Check prerequisites:
   - the Codex CLI is authenticated (`codex login status`); otherwise write `SKIPPED_NO_RUNNER` to PROGRESS.md and stop
   - fixtures exist (`uv run cre fixtures check --kind <K>`)
3. Run `uv run cre learn run --kind <K> --tag <date>-<K>`. It creates `autoresearch/<tag>`, loops within budget, and writes `results.tsv`.
4. Analyst sessions run via `CodexRunner`. **You (Devin) never act as the analyst and never read truth files.** Scoring is a separate process.
5. Only `brain/**` may change. Never touch `evals/`, gates, `tests/protected/`, config budgets, or `program.md`.
6. At the end:
   - open one PR with the results summary and five sampled outputs from `learning/review/`
   - append a PROGRESS.md entry
   - never merge it yourself
