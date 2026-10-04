# T021: CMBS gold-pair builder

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M2: Data and evals (branch `milestone/M2`) |
| Depends on | T020 |
| Read first | EVALS §2 set C |
| Allowed to modify | `evals/cmbs/**`, `src/cre_brain/data/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Match multifamily loans across Annex A-1, A-3 and EX-102 into gold records.

## Acceptance criteria
- [ ] AC1: Discover CMBS deals and collect Annex A-1 tables (HTML/PDF) and A-3 narratives for multifamily properties
- [ ] AC2: Match each property to its EX-102 monthly history (by deal + asset number/name); record the securitization figures and later outcomes
- [ ] AC3: Output `evals/cmbs/gold/*.json` with documents, ground-truth fields and outcomes; anonymization pass per EVALS §3
- [ ] AC4: ≥5 offline fixtures committed; `cre evals build-cmbs --limit N` builds more when network and keys exist (target ≥200)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k cmbs
```

## Done when
All ACs are met, verify exits 0, `passes` for T021 is set to true, the task branch is merged into `milestone/M2`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
