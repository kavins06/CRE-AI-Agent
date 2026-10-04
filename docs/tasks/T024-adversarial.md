# T024: Adversarial and contradiction set

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M2: Data and evals (branch `milestone/M2`) |
| Depends on | T022 |
| Read first | EVALS §2 set F |
| Allowed to modify | `evals/adversarial/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Prompt-injection, contradictory and missing-document cases.

## Acceptance criteria
- [ ] AC1: ≥60 cases: hidden or white text and metadata injections in OM PDFs, instructions in lease exhibits, contradictory rent rolls vs. T-12s, missing documents, out-of-buy-box deals
- [ ] AC2: Each case has an expected safe behavior label
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k adversarial
```

## Done when
All ACs are met, verify exits 0, `passes` for T024 is set to true, the task branch is merged into `milestone/M2`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
