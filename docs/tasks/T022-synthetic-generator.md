# T022: Synthetic deal generator

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M2: Data and evals (branch `milestone/M2`) |
| Depends on | T013, T020 |
| Read first | EVALS §2 set A |
| Allowed to modify | `evals/generator/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Latent deal sampler and document renderers with code-derived ground truth.

## Acceptance criteria
- [ ] AC1: The sampler is calibrated from T020 priors (Cook County, ACS, HUD, FRED); seeds are reproducible
- [ ] AC2: Renderers: rent roll in 3 layouts (XLSX/CSV), T-12 XLSX, OM PDF, lease PDFs; optional scanned/noisy variant
- [ ] AC3: Ground truth JSON computed with `cre_brain.finance`, never by an LLM
- [ ] AC4: `cre evals gen --n 50 --seed 1` writes deal packages + truth
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k generator
```

## Done when
All ACs are met, verify exits 0, `passes` for T022 is set to true, the task branch is merged into `milestone/M2`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
