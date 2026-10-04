# program.md: autoresearch charter for the CRE analyst brain

> The product is an autonomous CRE acquisition analyst. This file is the charter for its self-improvement loop, modelled on Karpathy's autoresearch `program.md`. **Only a human edits this file.** It is protected by CODEOWNERS.

## Setup
1. Agree a run tag, for example `oct04-ic_memo`. Create the branch `autoresearch/<tag>` from `main`.
2. Read `docs/LEARNING.md`, `brain/`, and the fixture manifest for the target deliverable kind.
3. Check that the frozen fixtures exist: `uv run cre fixtures check --kind <K>`.
4. Create `results.tsv` with only the header row. It is not committed.
5. Confirm a live model key is present. If none is, write `SKIPPED_NO_KEY` to `PROGRESS.md` and stop.

## What you may edit
- `brain/skills/**`, `brain/prompts/**`, `brain/playbook/global.md`. Edit **one artifact per experiment**.

## What you must not edit
- `evals/**`, `src/cre_brain/gates/**`, `tests/protected/**`, `config/gates.yaml`, `config/budget.yaml`, this file.
- Do not add dependencies.
- Do not read anything under `evals/holdout/`.

## Goal
Maximize the primary score for deliverable kind K on the dev split, without violating any counter-metric tolerance.

| Kind | Primary score | Counter-metrics (max allowed worsening) |
|---|---|---|
| SCREEN | decision agreement + critical-field accuracy | latency +10%, cost +10%, question rate +0.05 |
| UW_MODEL | assumption in-band rate + parity pass + value error | cost +10%, false flags +0.1/deal |
| IC_MEMO | rubric pass rate (calibrated judge) + provenance 100% | length +15%, cost +10% |
| DD_TRACKER | defect recall (critical-weighted) | false flags +0.1/deal |
| LOI | policy compliance + completeness | none |
| any | n/a | escalation rate +0.03 |

## Budget per experiment
- `max_metric_calls` = 40 per candidate (k=3 over the dev fixtures for K).
- Kill any experiment that runs longer than 20 minutes wall-clock and log it as `crash`.
- Nightly cap: `config/budget.yaml:nightly_usd`. Stop cleanly when it is reached.

## Output format
Append one row per experiment to `results.tsv` (tab-separated):
```
commit	kind	score	ci_low	cost_usd	status	description
```
`status` is one of `keep`, `discard`, `crash`. `ci_low` is the Bonferroni-adjusted lower bound of the paired improvement.

## Keep or discard
Apply `learning/keep_rule.py` exactly (see LEARNING §3).
- **Keep:** the branch advances.
- **Otherwise:** run `git reset --hard` back to the last kept commit.
- **Simplicity criterion:** a tiny gain bought with a much longer artifact is not worth it; an equal score with a shorter artifact is a keep.

## Loop
Never stop to ask a human. Continue until the budget is exhausted. Then:
1. Open one PR titled `autoresearch/<tag>: <K> <old>→<new>`, with the `results.tsv` summary and five sampled outputs.
2. Append a summary entry to `PROGRESS.md`.

Never merge your own PR.
