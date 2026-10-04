# HUMAN SETUP: owner checklist before and during Devin's build

> The product is an autonomous CRE acquisition analyst. Devin is the coding agent that builds it from this repo. Do these steps once, before the first overnight run.

## 1. GitHub protection (do this first)
- [ ] Turn on branch protection for `main`:
  - require PR review from a code owner
  - require these status checks: `check`, `protected-hashes`, `test-count`, `verify-features`
  - no force pushes
  - Devin's token must not be able to bypass these rules
- [ ] Confirm that `CODEOWNERS` lists you as the owner of the protected paths.
- [ ] Add the GitHub Actions secret `EVAL_SEALED_SEED`, a random 32-byte hex string. The sealed test set is generated from it in CI only.

## 2. Devin configuration
- [ ] Connect the repo and point Devin at `main`.
- [ ] Turn off **"wait for plan approval"** so overnight runs don't stall.
- [ ] Per-session ACU cap: about 10. Use many short sessions, not one giant one.
- [ ] Repo Secrets, as env var names only; Devin injects the values:

| Secret | Required? | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | Required for live runs | Without it, everything builds and tests on recorded transcripts, but live evals and the learning loop skip |
| `OPENAI_API_KEY` or `GOOGLE_API_KEY` | Optional | Cross-family verifier and judge; M6 OpenAI runner |
| `TYPESAFE_API_KEY` | Optional | Jev |
| `SEC_USER_AGENT` | Required | Your company name plus a contact address, as the SEC requires |
| `FRED_API_KEY`, `CENSUS_API_KEY`, `HUD_API_TOKEN`, `BLS_API_KEY` | Recommended | Free public data keys |
| `SOCRATA_APP_TOKEN` | Optional | Avoids throttling on county open-data portals |
| `REDUCTO_API_KEY`, `MS_GRAPH_*` | Later | Licensed extraction and real Excel recalculation |

- [ ] Optional: let a coordinator session hand independent tasks to child Devins. `feature_list.json` dependencies show which tasks can run in parallel.

**Remember:** Devin's ACUs pay for Devin's own work. The analyst's model calls during evals and learning are billed to the API keys above. The nightly cap is `config/budget.yaml:nightly_usd`, $25 by default.

## 3. Infrastructure handoff (your team)
- [ ] Your per-user computer must satisfy the **box image contract** in `docs/SPEC.md` §3. Implement the `SandboxProvider` Protocol for your infrastructure. Devin ships a local Docker reference implementation and contract tests that you can run against yours.
- [ ] Per-tenant encryption keys, network egress allowlists and secret injection belong to the infrastructure. See SPEC §3 and §15.

## 4. Each morning
1. Read `PROGRESS.md`. It has one entry per session, plus any BLOCKED items with evidence.
2. Review the milestone PRs. Check the CI output and the `verify` output pasted in each PR.
3. Review any `autoresearch/*` PR. Check the `results.tsv` summary and the sampled outputs in `learning/review/`.
4. Answer any questions Devin left in `PROGRESS.md` under "Needs owner".

## 5. When you have real deals
- Put them in the deal inbox (`inbox/` in a user box, or `POST /tasks` with files).
- Correct the agent's outputs through `POST /corrections`. Each correction becomes training signal (see `docs/LEARNING.md` §6).
- Mark 10–20 past deals as the **Reality Set**, with your assumption ranges and decisions. From then on they become the most important eval.
