# program.md: autoresearch charter for the CRE analyst brain

> The product is an autonomous CRE acquisition analyst. This file is the charter for its self-improvement loop, modelled on Karpathy's autoresearch `program.md`. **Only the owner edits this file** (it is a protected path).

## Setup
1. Agree a run tag, for example `oct04-uw_model`. Create the branch `autoresearch/<tag>` from `dev`.
2. Read `docs/LEARNING.md`, `brain/`, and the fixture manifest for the target kind K.
3. Check that fixtures exist: `uv run cre fixtures check --kind <K>`.
4. Create `results.tsv` containing only the header row. It is never committed.
5. Check `codex login status`. If it fails, write `SKIPPED_NO_RUNNER` to `PROGRESS.md` and stop.

## What you may edit
- `brain/skills/**`, `brain/prompts/**`, `brain/playbook/global.md`. **One artifact per experiment.**

## What you must not do
- Edit any path in `scripts/protected_paths.txt`.
- Add dependencies.
- Read eval truth, `evals/` scorer internals during an analyst session, or anything in the private eval repo.
- Act as the analyst. Analyst work runs only through `CodexRunner` in repo-less containers.

## Goal
Maximize the primary score for K on the dev fixtures without violating any counter-metric tolerance.

| Kind | Primary score | Counter-metric tolerances (max worsening) |
|---|---|---|
| SCREEN | buy-box input accuracy + critical-field accuracy | latency +10%, tokens +10%, question rate +0.05 |
| UW_MODEL | NOI/value error vs. truth + assumptions in-band + parity pass | tokens +10%, false flags +0.1/deal |
| IC_MEMO | number provenance + required sections (+ judge, once calibrated) | length +15%, tokens +10% |
| DD_TRACKER | critical-weighted defect recall | false flags +0.1/deal |
| LOI | policy compliance + completeness | none |
| any | n/a | escalation rate +0.03, stuck events +0 |

## Budget
- **Per experiment:** dev fixtures n = 10 (or the minimum n reported by the keep-rule power test), k = 3, about 30 analyst sessions. Kill the experiment at **3 h** wall-clock and log it as `crash`.
- **Nightly:** `config/budget.yaml` caps `nightly_sessions` (default 200) and `nightly_wallclock_h` (default 10). Stop cleanly at whichever comes first.
- With a shared Codex login, run one serialized job stream (`codex_login_max_concurrency: 1`).

## Output format
`results.tsv`, tab-separated, one row per experiment:
```
commit	kind	score	ci_low	sessions	status	description
```
`status` is `keep`, `discard` or `crash`. `ci_low` is the Bonferroni-adjusted lower bound of the paired improvement.

## Keep or discard
1. Run `learning/keep_rule.py` `dev_pass`.
2. If it passes, run the holdout confirmation through the scoring service.
3. **Keep:** the branch advances.
4. **Otherwise:** `git reset --hard` to the last kept commit.

**Simplicity:** on a tie, the shorter artifact wins.

## Loop
Never stop to ask a human. Run until a cap is reached. Then:
1. Open one PR, `autoresearch/<tag>` → `dev`, with the results summary and five sampled outputs from `learning/review/`.
2. Append a summary to `PROGRESS.md`.
3. Never merge your own PR.
