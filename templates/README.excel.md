# Multifamily Excel reference

Build the reproducible functional template and cell map from the installed package:

```sh
uv run --locked python -m cre_brain.excel.build_template --output templates --config config
```

`mf_standard.xlsx` is a five-year, monthly unlevered operating pro forma, matching
`finance.proforma.build_proforma` without optional tax/value-add schedules. It
contains seven named fact inputs, 480 monthly outputs and 30 annual outputs.
The JSON map records fact keys and calculation namespace/output keys, absolute
cells, names, formulas, functions, units and input/output roles. Runtime calculation
IDs are supplied explicitly; reusable templates never bake in a deal's IDs.
`SUM` is the only function required by this template. Validation uses the supplied
`GateSettings.excel_functions` whitelist and checks the complete formula DAG.

`build_workbook(template, mapping, target, engine=..., scope=..., deal_id=...,
task_id=..., calculations={"proforma": stored_calc_id}, gates=..., as_of=...)`
resolves latest facts by tenant/deal/key and calculations by stored identity. It
rejects missing/ambiguous/conflicting records, stale graph items, expired/not-yet-valid
facts, unresolved/cyclic/cross-deal calculation lineage, incompatible units/types,
and stored pro forma outputs inconsistent with current facts. The calculation's
stored input lineage must cover all seven mapped facts; upstream callers must
persist their explicit input identities rather than an unstored assumption bundle.
The reference map supports exactly one calculation namespace, `proforma`.
Every reachable fact, including unmapped upstream facts, must belong to the deal,
be nonconflicting and nonstale, have valid time containing `as_of`, and have a
timezone-aware `known_at` no later than the end of that date in UTC (inclusive).
Omitting `as_of` uses today's UTC date; naive knowledge timestamps are rejected.
Use new calculation IDs when regenerating stale calculations. Divergent versions
of a calculation ID are rejected. Invalidated identities remain stale across tasks
within the tenant; task-specific event ordering is unchanged. The current graph
has no stale-clear API.

`WorkbookBuild` returns the saved input workbook, validated mapping, authoritative
Decimal expectations and per-cell provenance with exact mapping coverage.
Comments retain fact versions/claim types/document anchors
and calculation IDs/output keys/code versions/dependencies. Formula outputs remain
formulas. Inputs must be finite and round-trip through Excel's 15-significant-digit
representation; excessive precision/overflow/underflow fails before writing.
The existing deterministic finance function validates stored reference outputs;
its transient validation result is never used as deliverable evidence.

The product deliverable path is
`recalc_deliverable(build, LibreOfficeEngine(config, gates=...), gates=...)`
from `cre_brain.excel.deliverable`, returning `(recalculated_path, gate_result)`.
Use the descriptor returned by `build_workbook`; caller-created expectations are
not authoritative. The helper revalidates the descriptor, requires exact mapped
expectation/provenance coverage, and checks mapped names, destinations, input roles
and output formulas before and after recalculation. Only case changes, equivalent
sheet quoting and absolute cell markers at a fixed formula address normalize;
changed constants, operators, range boundaries and operand order fail closed.
**The returned recalculated XLSX is the deliverable only when its gate passes.**
Never save a workbook opened with
`data_only=True`. UNO explicitly invokes `calculateAll()` and stores with the
`Calc MS Excel 2007 XML` filter. The source is copied, unique HOME/TMPDIR/profile
and pipe are allocated, and parent credentials/configuration are not inherited.
Macros are disabled with UNO's symbolic `MacroExecMode.NEVER_EXECUTE` constant.
The worker privately captures and discards a bounded Office stderr tail. Its
interruption handlers are installed before Office creation. It has a bounded
connection wait and parent timeout, and terminates only processes it creates.
On POSIX, the helper owns a new session/process group; the parent sweeps that
owned group after graceful cleanup, including early helper exit and interruption.
Cleanup has up to 15 additional seconds after the client timeout. Parent helper
stderr is discarded; caller errors are fixed failure categories without native
stderr, exception text or chained native diagnostics. It refuses outputs
with changed/lost formulas or any formula cache equal to `None`. Formula errors remain in
the output for parity to report with addresses.

Parity passes when `abs(actual - expected) <= max(parity_abs,
parity_rel * abs(expected))`, including equality. Both thresholds come from the
supplied validated `config/gates.yaml` settings. Exact rational comparisons avoid
caller Decimal-context rounding. Every Excel error cell is reported, including
`#REF!`, `#DIV/0!`, `#VALUE!` and `#NAME?`; empty/nonnumeric mapped caches fail.
The low-level `check_parity(path, expected, gates=..., mapping=...)` requires exact
coverage and intact formulas when a mapping is supplied. Without a mapping it
only compares a numeric subset and scans error cells; that result is not a
deliverable gate. Likewise `ExcelEngine.recalc(path)` alone cannot establish
build-bound parity. Product callers must use `recalc_deliverable`.

## UNO runtime configuration

Install LibreOffice and Python UNO in the approved runtime, not implicitly from
product code. Native installations normally use `soffice` on PATH and
`/usr/bin/python3`; overrides support relocated runtimes:

| Environment variable | Value |
| --- | --- |
| `CRE_EXCEL_SOFFICE` | Office executable |
| `CRE_EXCEL_UNO_PYTHON` | UNO-compatible Python executable |
| `CRE_EXCEL_LIBRARY_PATHS` | Colon-separated library directories, Office program directory **first**, architecture libraries second |
| `CRE_EXCEL_UNO_PATHS` | Colon-separated Python UNO directories, including dist-packages and Office program directory |
| `CRE_EXCEL_URE_TYPES` | Colon-separated paths to offapi.rdb and oovbaapi.rdb |
| `CRE_EXCEL_TIMEOUT_S` | Integer total client timeout, 1–60 seconds (default 60) |

These become a minimal worker environment; office itself receives neither the
client's PYTHONPATH nor URE_MORE_TYPES. Local Unix socket binding must be permitted:
LibreOffice's pipe transport and instance management require it. A restricted
sandbox that rejects AF_UNIX bind cannot execute this integration; do not bypass
that restriction or substitute a skip for real recalculation evidence.

Run tests serially; the repository uses a fixed pytest basetemp:

```sh
uv run pytest tests/excel -q -k template && uv run python scripts/check_task.py T019
uv run pytest tests/excel -q && uv run python scripts/check_task.py T020
make check
```

The standalone hosted Excel workflow installs an approved native runtime and runs
both exact verifiers. Its execution remains coordinator-owned after publication.

## Scope and execution boundary

This reference currently excludes optional tax/value-add schedules, debt sizing,
waterfalls and return calculations. Those remain in authoritative finance modules;
firm onboarding/expanded templates must explicitly map their labelled stored
calculation inputs and formula outputs. Unsupported features fail before native
processing: macros, external relationships/links, iterative/circular calculations,
data tables, shared/array formulas, structured tables, embedded objects, pivot
and connection features, non-whitelisted functions, unresolved names, oversized
packages/cell ranges and extension features. Worksheet-local defined names are
rejected. Macro-enabled content types and VBA/macro-sheet relationship types are
rejected independently of filenames.
The only supported extension is the exact workbook-level LibreOffice
`extCalcPr` metadata subtree declaring `stringRefSyntax="ExcelA1"`. Other
extension URIs, attributes, children, locations and reference syntaxes fail
closed; this permits native export without ignoring arbitrary extensions.

This feature scan is **not an untrusted-workbook sandbox**. Native parsing here is
for trusted synthetic fixtures only; production seller/firm uploads require the
future contained execution boundary. State reads assume an upstream serialized
build; they are not a transactionally frozen concurrent-state snapshot.

`GraphExcelEngine` is an explicit licensed stub. Its separate licensing probe uses
`requires_license(MS_GRAPH)`; real LibreOffice AC tests have no prerequisite skip.
Registry/MCP/CLI-tool registration and recorded runner/FakeRunner plumbing are
intentionally deferred to T032/T033 and the later runner/deliverable tasks. No
server exists yet, and no transcript or analyst-quality evidence is generated.
