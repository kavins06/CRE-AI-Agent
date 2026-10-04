# T033 source handoff

This implementation supplies source architecture and **synthetic plumbing-only**
tests. It supplies no isolated live runtime, recorded production transcript,
analyst-quality evidence, or task acceptance. T033 and T030 must remain false.
The coordinator owns task status, integration, and acceptance.

`SegmentSpec` and `Workspace` are host-owned typed boundaries. `CodexRunner`
generates deal-local `AGENTS.md`, `.agents/skills/`, and `.codex/config.toml` from
the trusted brain and configured lead role, with optional host-authenticated firm
summary/user memory. Only that explicit asset set is staged; no repository,
evaluation truth, raw seller documents, host configuration, or credentials are
copied. Model/provider values come from host configuration, without fallback IDs.

`StreamingAdapter` extends the existing `SandboxProvider` without changing its
public protocol. It must use the **same** canonical T032 `ToolRegistry`, verify
containment/auth/effective capabilities independently, stage only approved assets,
stream bounded JSONL, enforce turn/token caps before further model usage, and
cancel the complete process lifetime boundary. `CancellationReceipt` provides
independently metered total tokens, including interrupted turns. A missing or
inconsistent total makes usage incomplete; subsequent segments fail closed.
Unconfirmed descendant cleanup leaves the segment active and requires recovery.
Buffered `SandboxProvider.exec` is never used as an analyst fallback.

The candidate exec/resume arguments and TOML require verification against the
installed CLI in the restricted runtime. Config intent is not capability evidence.
The owner adapter must supply isolated HOME/CODEX_HOME, appropriate authorized
authentication outside generated assets, native caps, reliable termination,
backpressure/output bounds, and an MCP launcher bound to the existing host registry.
A standalone `cre mcp serve` cannot construct that authority: T032's host factory
must be installed by trusted composition. The current buffered local provider
cannot satisfy this adapter contract. No adapter is implemented or claimed here.

`Normalizer` rejects duplicate keys, nonfinite/deep/oversized/malformed JSONL,
invalid usage, repeated completed items, and changing session identity. Unknown
provider types are preserved as sanitized unsupported `runner_raw` events;
FakeRunner refuses them. Cached input is a subset of input tokens, never added
again. Registered secrets and credential patterns are scrubbed before persistence
or streaming. The host secret provisioner must register exact secret values;
the runner never reads authentication files or ambient credentials.

All runner events, session bindings, token charges, segment reservations, and
recording authenticity bindings use the existing append-only tenant EventStore
and T032 transaction/policy seams. There is no second authoritative state store.
Resume checks tenant/task/deal/box/release bindings, immutable segment numbers,
active segments, and cumulative usage/deadlines. Authoritative tool/control events
can end segments on finalization, questions, confirmation, interrupt/pause/stuck.
Control events are inspected at stream boundaries; immediate external interruption
still requires the owner's adapter/control-plane cancellation wiring.

`cre record` uses an import-safe built-in registrar, alongside knowledge,
tools/MCP, release, and `evals gen`; plugin discovery behavior is preserved. The host
installs `install_record_factory` after authentication. Without it the command
refuses. `record_segment` observes actual adapter output, publishes new files with
exclusive no-follow writes and manifest last, and persists the manifest hash in
canonical events. `--refresh` creates a new recording at a new output path; it
never edits existing evidence. Failed, unclean, or unmetered recordings refuse.
Synthetic captures are explicitly labeled and prohibited under `transcripts/`.

The manifest binds CLI/adapter/event-schema versions, release, scope, session,
model/provider, generated instruction hash, and raw/event hashes. `raw.jsonl` is
**sanitized provider JSONL**, not byte-identical secret-bearing stdout. Its hash
verifies stored bytes. `source_raw_sha256` hashes the exact captured validated
source frames transiently; source bytes are not retained. Budget-limited captures
may be prefixes. This source digest cannot be recomputed from sanitized artifacts.
Hashes detect corruption; the separate canonical manifest binding authenticates
recordings even if an attacker rehashes edited files. Independently imported
records require an explicit trusted manifest hash from the embedding host.

`FakeRunner` replays supported CRE calls through T032. It matches the tool and
argument keys, ignores provider call/result IDs, and permits a typed host-owned
reference-ID adapter. Canonical request IDs provide real-tool idempotency. It
preflights every call before effects, refuses redacted arguments, unknown/shell
operations and external sends, and compares response status rather than brittle
full output/ID snapshots. Host fixtures must supply the actual artifacts/evidence;
replay does not recreate shell-produced files. Final assertions recheck canonical
final versions, artifact bytes/freshness, required blocking gates, and trusted
release events. Empty expected final state fails. This proves plumbing only.

Unresolved prerequisites: genuine T030 restricted-runtime/capability/auth evidence;
a trusted streaming adapter with preventive native metering/cancellation and MCP
composition; and owner-configured runtime model/provider. The T032 snapshot/gate
repairs are composed here, but do not establish live runtime evidence.
The existing prompt/config placeholders
are not an operational brain. The `requires_codex` test here is a refusal contract,
not a successful live recording or analyst evidence. No production transcript was
created, edited, or committed. Tests never invoke live models or containers.

```bash
uv run pytest tests/runner -q -k 'codex or fake' && uv run python scripts/check_task.py T033
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy --strict src/cre_brain/runner
make check
```

Use distinct `--basetemp` paths for overlapping pytest runs; this repository's
default is a shared directory within each checkout. Clearing it during another
run destroys that run's fixtures. Same-session final coordinator results are
recorded in `PROGRESS.md`. Passing synthetic tests cannot authorize T033 acceptance.
Recovery/accounting reconciliation and immediate control-plane cancellation still
require trusted runtime integration.
