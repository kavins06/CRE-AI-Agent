# HUMAN SETUP: owner checklist before and during Devin's build

> The product is an autonomous CRE acquisition analyst. Devin is the coding agent that builds it from this repo. Do these steps once, before the first overnight run.

## 0. Before Devin's first session (required)
- [ ] Confirm that **`@kavins06` in `CODEOWNERS` is your GitHub handle**. Edit it if not. GitHub silently ignores invalid owners.
- [ ] A **`dev` branch** exists (created from `main` with this package). Devin works only on `dev`.
- [ ] Create the label **`protected-change`** in the repo. Only you apply it.
- [ ] Create a **private repo `cre-ai-agent-evals-private`** that Devin cannot access. Add a CI secret `EVALS_PRIVATE_TOKEN` (read-only) to this repo. Put holdout and sealed seeds there (`seeds.yaml`: random 64-bit integers per split). Later, add your labels and real deals there too.
- [ ] Decide **Codex auth**:
  - your existing login is fine for development on public and synthetic data, as one serialized job stream
  - use **API-key auth** for anything with customer data, parallel runs, or production
  - record your data-processing position here: ______

## 1. GitHub protection
- [ ] Turn on branch protection for `main`:
  - require PR review from a code owner
  - require these status checks: `protected-paths` (owner-authored `guards.yml`), plus `check` and `test-count` once Devin adds them in T002
  - no force pushes
  - Devin's token must not be able to bypass these rules
- [ ] Turn on "Require review from Code Owners".

## 2. Devin configuration
- [ ] Connect the repo and point Devin at the **`dev`** branch.
- [ ] Turn off **"wait for plan approval"** so overnight runs don't stall.
- [ ] Per-session ACU cap: about 10. Use many short sessions, not one giant one.
- [ ] Repo Secrets, as env var names only; Devin injects the values:

| Secret | Required? | What it does |
|---|---|---|
| *(none for models in v1)* | n/a | The analyst runs on the **Codex CLI**, which you install and authenticate on the build machine and in boxes. The brain is trained through it |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Later | Only when the commercial SDK runners are added (M8) |
| `TYPESAFE_API_KEY` | Optional | Jev |
| `SEC_USER_AGENT` | Required | Your company name plus a contact address, as the SEC requires |
| `FRED_API_KEY`, `CENSUS_API_KEY`, `HUD_API_TOKEN`, `BLS_API_KEY` | Recommended | Free public data keys |
| `SOCRATA_APP_TOKEN` | Optional | Avoids throttling on county open-data portals |
| `REDUCTO_API_KEY`, `MS_GRAPH_*` | Later | Licensed extraction and real Excel recalculation |

- [ ] Optional: let a coordinator session hand independent tasks to child Devins. `feature_list.json` dependencies show which tasks can run in parallel.

**Remember:**
- Devin's ACUs pay for Devin's own work (building).
- The analyst's sessions during evals and learning run on the **Codex CLI** under whatever account you authenticated it with.
- Nightly caps are in `config/budget.yaml`: `nightly_sessions` (default 150) and `nightly_wallclock_h` (default 8).
- [ ] Confirm `codex login status` succeeds on the machine Devin uses.

## 3. Infrastructure handoff (your team)
- [ ] Your per-user computer must satisfy the **box image contract** in `docs/SPEC.md` §3. Implement the `SandboxProvider` Protocol for your infrastructure. Devin ships a local Docker reference implementation and contract tests that you can run against yours.
- [ ] Per-tenant encryption keys, network egress allowlists and secret injection belong to the infrastructure. See SPEC §3 and §15.

## 4. Each morning
1. Read `PROGRESS.md`. It has one entry per session, plus any BLOCKED items with evidence.
2. Review the `dev` → `main` milestone PRs. Check the CI output and the `verify` output pasted in each PR. If the PR touches protected paths, review those diffs closely before you add `protected-change`.
3. Review any `autoresearch/*` PR. Check the `results.tsv` summary and the sampled outputs in `learning/review/`.
4. Answer any questions Devin left in `PROGRESS.md` under "Needs owner".

## 5. When you have real deals
- Put them in the deal inbox (`inbox/` in a user box, or `POST /tasks` with files).
- Correct the agent's outputs through `POST /corrections`. Each correction becomes training signal (see `docs/LEARNING.md` §6).
- Mark 10–20 past deals as the **Reality Set** in the private eval repo, with your assumption ranges and decisions. From then on they are the most important eval.
- Use the labelling queue (`cre label`, T061) for about 2 hours a week. Judges need ≥150 labels per critical item before they can gate anything.
