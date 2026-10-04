# PROGRESS: session log (append-only)

> The product is an autonomous CRE acquisition analyst. Every coding-agent session appends one entry. Never edit or delete past entries.

## Decisions
<!-- Unspecified choices made during the build, each with a one-line rationale. -->

## Needs owner
<!-- Blockers that need the owner: missing secrets, licences, spec questions. -->

## Log

### Template
```
### YYYY-MM-DD HH:MM UTC: T### <title>
- Branch: m<milestone>/<task-id>-<slug>
- Changed: <files/areas>
- Verify: <command> → exit 0
  <last 30 lines of output>
- Next: <next task id>
- Blockers: none | BLOCKED: <evidence, what is needed>
```

### 2026-10-04: Planning package created
- Docs, task list and guards specified. No code yet. Start with T001.

### 2026-10-04: Runner switched to Codex CLI; OpenHands-derived fixes
- The v1 analyst runner is the Codex CLI (`CodexRunner`). The brain is trained through it without separate model keys. Claude Agent SDK and OpenAI SDK runners move to M6 (pre-commercial).
- Policy and gates moved into the runner-agnostic `cre` tool server (MCP + CLI). OS-level limits are the primary enforcement.
- Added from the OpenHands review:
  - AgentEvent schema
  - interrupt / pause / resume / mid-task messages
  - confirm-before-act toggles (off / ask / on)
  - stuck detection
  - event redaction
  - API auth and tenant scoping
  - box agent (cre-boxd) with idempotent resume and disk-loss recovery
  - browse tool
  - parallelism limits
  - stress tests
- Blind scoring rule: the builder never acts as the analyst, and truth is materialized only after deliverables are committed.

### 2026-10-04: Adversarial review applied (pre-handoff)
- Branch model: Devin works on `dev`; each milestone is a PR `dev` → `main`; task state lives on `dev`.
- Owner-authored guards are in place before T001:
  - `CODEOWNERS` (@kavins06, to be confirmed)
  - `.github/workflows/guards.yml`
  - `scripts/protected_paths.txt` and `scripts/check_protected.py`, which read the list from the base branch; changes need the `protected-change` label
- Blind scoring is enforced physically:
  - the analyst runs in a repo-less container
  - truth is written to a separate directory
  - holdout and sealed sets live in the private repo `cre-ai-agent-evals-private` and are scored by a CI service
  - FakeRunner is plumbing only; transcripts come only from `cre record`
- Codex runner rewritten around verified behaviour:
  - the container is the sandbox
  - one throwaway extraction container per document, with no MCP
  - raw documents are not mounted for the analyst
  - pending (non-blocking) confirmations
  - API-key auth for customer data
- Learning loop:
  - no DSPy/LiteLLM; GEPA is a one-candidate proposer with a Codex LM
  - realistic budgets
  - keep-rule acceptance defined statistically
- Task list re-scoped to 71 tasks:
  - thin slice first: M2 is SCREEN + UW_MODEL through `cre run`
  - large tasks split; every AC needs a named test (`check_task.py`); approved skip markers only
- Added analyst capabilities: tax reassessment, value-add, JV waterfall, debt quotes, refi/hold-sell, rent comps (honest proxies), rent regulation, multi-deal tasks, deliverable versioning + user-edit ingestion.
- DBOS replaced by a Postgres jobs table with idempotent segments. Event `seq` is assigned by the control plane; the box uses `origin` for acks.
