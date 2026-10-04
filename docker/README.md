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
