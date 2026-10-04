# Local sandbox reference

Build from the repository root with a Linux Docker daemon:

```sh
docker build -f docker/box/Dockerfile -t cre-box:local .
docker build -f docker/extract/Dockerfile -t cre-extract:local .
docker build -f docker/egress/Dockerfile -t cre-egress:local .
uv run pytest tests/sandbox -q
uv run python scripts/check_task.py T031
```

The daemon must support cgroups, network namespaces and iptables. Provision at
least 20 GB persistent storage per analyst; named volumes persist across
`sleep`/`resume` and are deleted by `destroy`. Defaults are the SPEC minimum
2 CPUs / 4 GB for **one** parallel analyst session. Configure 4 CPUs / 8 GB
when allowing two sessions. Production owners enforce storage quotas and use
their own provider/images; this is a local reference, not a hosted service.

`DockerConfig` chooses approved images, namespace, daemon socket, state directory,
CPU/memory/PID limits, exact HTTPS domains and extraction-only model domains.
No wildcard, IP literal or private DNS answer is accepted. Prefer immutable image
digests outside local development. The analyst never receives Docker socket access;
trusted orchestration launches extraction boxes through `create_extraction`.
Extraction accepts a pre-parser's bounded JSON object, never a raw document.
Its only source bind is read-only parsed JSON; no analyst memory, firm skills or
MCP configuration is mounted.

The sidecar installs a deny-by-default firewall with startup-only capabilities,
then irrevocably drops all capabilities and runs the CONNECT proxy as UID 1001.
The analyst runs as UID 1000, sharing only its dedicated sidecar network namespace.
UID 1000 can connect only to the loopback proxy, even if application proxy
variables are removed. Proxy DNS configuration is a read-only sidecar bind,
not an analyst mount. Root filesystem, firm/config paths and capabilities remain
restricted; only deals, outbox, memory and scratch volumes are writable.

Pass a trusted per-user `secrets` callable to `LocalDockerProvider`. Only
`CODEX_API_KEY`/`OPENAI_API_KEY` are accepted, only for an individual `exec` call.
They are not image layers or container configuration. Returned output is redacted.
Snapshots include only bounded regular workspace files and reject symlinks,
hardlinks, known runtime secret values and credential-file names. This is a
refusal mechanism, not arbitrary encoded-secret detection; untrusted code must
never be granted unrelated host credentials.

The reusable owner contract exercises direct shell commands with no tool policy:

```sh
uv run python -m tests.sandbox.contract --factory owner_module:factory --image owner-image
```

The production `SandboxProvider` interface stays unchanged. Artifact inspection
uses the separately published `SnapshotReader` protocol in `sandbox/base.py`:
`async read_snapshot(snapshot_id: str) -> bytes`. `LocalDockerProvider` implements
it with owned, bounded, no-follow, content-hash-checked reads. Owners whose
provider uses opaque remote snapshot handles supply a trusted reader via
`--snapshot-reader-factory owner_module:reader_factory`; programmatic callers
use `SnapshotContractAdapter(provider, reader)` with `run_contract`.
Readers must return the actual TAR artifact, not a manifest or prefiltered view.
No artifact reader is exposed to analyst code. The contract inspects bytes; it
does not restore/extract archives. It bounds the full decoded TAR, scans names,
PAX metadata and payloads for its synthetic credential canary, rejects aliases
and duplicate destinations, and accepts single-stream TAR/GZIP/BZIP2/XZ within
its size/memory bounds. Unsupported or concatenated compression fails closed.
Entries must be non-sparse regular files. The contract locates termination from
the last validated file's physical TAR data offset, requires both zero end
blocks and rejects any non-padding trailing data, including malformed headers
that Python's TAR iterator can otherwise swallow.

For the local factory, set `CRE_SANDBOX_STATE`, `CRE_SANDBOX_NAMESPACE`,
`CRE_SANDBOX_IMAGE`, and optionally `CRE_SANDBOX_DOMAINS` (space-separated),
`CRE_SANDBOX_MODEL_DOMAINS`, `CRE_SANDBOX_DOCKER`,
`CRE_SANDBOX_PROXY_IMAGE`, `DOCKER_HOST`; use
`--factory cre_brain.sandbox.local:provider_from_env`. The CLI factory deliberately
injects no real credentials. The physical fixture builds default reference images
once per pytest process, so fresh CI feature verification needs no manual image
setup. Explicit `CRE_SANDBOX_*_IMAGE` choices are never rebuilt or replaced.
Missing daemons or custom images fail rather than skip or run host code;
`make check` excludes service integration tests.
