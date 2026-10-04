# T036 public synthetic generator v1

This is deterministic developer fixture work. Agreement with these answers is
agreement with this sampler and finance code, **not analyst-quality evidence**.
All defaults are uncalibrated; T050 owns public-data calibration. There are no
model calls, downloads, customer records or existing evaluation answers here.

From an editable source checkout, with the existing dev dependencies or the
`documents` extra installed:

```bash
uv sync --locked --python 3.12
uv run cre evals gen --n 20 --seed S --out-packages /tmp/packages --out-truth /tmp/truth
```

Both roots must be **new**, have existing parents, contain no `..` or symlink
components, and neither can contain the other. Existing empty directories also
cause rejection. `n` is an integer from 1 to 1000; seeds are nonempty strings of
at most 1024 characters. The command never invokes an analyst or a scorer.

## Default priors and units

All selections are discrete uniform draws unless stated otherwise. Money uses
Decimal, never floating point; ratio arithmetic uses an isolated precision-28,
half-even context with explicit exponent limits, flags and traps, independent
of both the active context and mutable `DefaultContext`. Public sampling and
rendering also isolate validation so caller signals are preserved. Money derived from ratios is rounded to cents. The sampler
uses a private `random.Random` initialized from SHA-256 of the JSON pair
`[seed, deal_index]`; it does not change global random state. Indexing starts at
1 and each index is independent of the requested batch size.

| Input | Default prior / rule |
|---|---|
| Unit count | 12–96 inclusive |
| Unit type | Equal probability of 1BR, 2BR, 3BR; independent of rent |
| Monthly market rent | USD 900.00–2400.00 inclusive, in cents |
| Property vacancy probability | 200–1500 basis points; each unit independently vacant |
| Contract discount for occupied units | 0–1200 basis points of that unit's market rent |
| Monthly concession | 0–500 basis points of occupied contract rent |
| Vacant unit | Contract rent and concession both zero |
| Other income | USD 15.00–60.00 per unit/month, in cents |
| Property tax | 800–1200 basis points of net collected revenue including other income |
| Insurance | 300–600 basis points of the same revenue |
| Utilities | 500–900 basis points of the same revenue |
| Repairs | 600–1000 basis points of the same revenue |
| Management | 300–500 basis points of the same revenue |
| Payroll | 700–1000 basis points of the same revenue |
| Replacement reserves | USD 15.00–40.00 per unit/month, in cents, **below NOI** |
| Revenue growth | 0–500 basis points annually |
| Expense growth | 100–500 basis points annually |
| Asking price | USD 80,000–250,000 per unit, whole-dollar draw |
| Vintage | 1940–2020 inclusive |
| T12 / as-of | Complete January–December 2025; as-of 2026-01-01 |

`DefaultPriors` exposes unit-count bounds, rent bounds, vacancy-probability bounds,
maximum contract discount and maximum concession. Bounds are validated, with
12–96 unit limits keeping document sizes bounded. The remaining documented
defaults are v1 sampler constants. `calibrated` must be false. Calibration must
version the sampling recipe and its metadata; editing these priors does not
establish that they describe real properties.

Generator unit IDs follow the exact canonical `U###` grammar (ASCII `U` plus
three ASCII digits), including custom latent models with valid content identities.
Formula prefixes, surrounding whitespace and noncanonical widths are rejected.

Every historical month repeats the same sampled operating state: v1 deliberately
has no seasonality, missing months, one-time items, defects or lease date modeling.
Asking price and vintage are independent, descriptive seller inputs; they are
not finance-derived valuations. No geographic claim is implied. Larger units do
not have a rent premium in this version.

Projection input revenue is **net collected rent after vacancy and concessions**
plus other income. Additional vacancy and credit-loss assumptions are zero to
avoid double deduction. Operating expenses already include property tax;
replacement reserves are excluded from expenses. The 12-month unlevered finance
projection reports NOI before reserves and cash flow after reserves. Growth is
rendered as an explicit assumption but has no effect in the first projection
year under `build_proforma`'s annual-step convention. There is no debt, renovation,
exit value or tax reassessment scenario in this slice.

## Rendered layouts and separation

Each `packages/deal-NNNN/` contains eight documents:

- `rent-roll-yardi.xlsx` and `.csv`: unit, floor plan, status, market rent, lease
  rent, concession.
- `rent-roll-realpage.xlsx` and `.csv`: unit type, apartment, market rent,
  discount, scheduled rent, occupancy.
- `rent-roll-broker.xlsx` and `.csv`: apartment number, occupancy, current rent,
  bedrooms, incentive, asking rent.
- `t12.xlsx`: nine accounts, twelve ISO-labeled calendar-month columns, positive
  expense costs, explicitly identified reserves below NOI.
- `om.pdf`: native text with property inputs and collection-basis projection
  assumptions, monetary units and ratio units.

These are **styled synthetic layouts**, not exports from the named vendors.
All variants describe the same units. The latent `layout` cycles yardi, realpage,
broker by index, allowing a future suite to choose one variant without changing
the data. For this task the package includes all variants to exercise every
renderer. XLSX money is stored as exact decimal **text**, avoiding openpyxl's
numeric Decimal-to-float conversion; CSV preserves the same lexemes. The native
extraction layer observes these strings without calculation. No formulas, hidden
sheets, links or embedded scripts are generated. OMs do not contain computed
answers or latent IDs.

Only `truth/` contains:

- `manifest.json`: seed, priors, generation recipe hash, pinned dependency/runtime
  versions, units, and deal IDs.
- `deal-NNNN.json`: validated latent inputs, input identity map, finance
  `CalcResult`s and SHA-256 hashes of the package documents.

Every computed answer is returned unchanged from `normalize_rent_roll`,
`normalize_t12` or `build_proforma`. No alternate financial scoring arithmetic
is implemented here. Raw sampled input values live in `latent` and `inputs`.
Input IDs bind deal and record identity to their exact source contents; mutation
without a new identity is rejected. `code_version` fingerprints all installed
finance and domain Python sources, including finance's decimal context.

**The analyst must receive only packages**, through the existing quarantined
pre-parser/extraction flow. Never mount or copy truth, the source repository,
seed metadata, staging directories, or scoring input identities into its session.
The generator does not configure runner mounts; that is a later harness task.
The seed is also excluded from document metadata and CLI success output.

## Determinism and output safety

On the same Python and pinned dependency/zlib runtime, repeated invocations with
the same seed, index and priors produce identical document and JSON bytes.
Tests compare two independently generated 20-deal batches, not just their totals.
CSV/JSON newline and ordering are fixed. XLSX core timestamps and ZIP member
timestamps/order are normalized. ReportLab uses `invariant=1` with uncompressed
page streams and a fixed font. There is no promise of identical bytes across
Python, zlib or library upgrades; versions and source hashes are retained so
changes are distinguishable. Random private staging names and filesystem
timestamps are intentionally nondeterministic and are not embedded in artifacts.

Linux `/proc/self/fd` and `renameat2(RENAME_NOREPLACE)` are required for publication.
The generator opens each parent component with `O_NOFOLLOW`, pins directory
descriptors, and rejects equal physical output identities as well as lexical
overlap. Each payload is inside a private mode-0700 job directory with a
retained descriptor. Publication uses distinct source-job and destination-parent
descriptors, checks the recorded payload type and identity, and does not resolve
the job through its mutable parent entry. Mode 0700 excludes other UIDs; it does
**not** sandbox root or same-UID adversaries. The identity check alone does not
protect against a same-UID process replacing a payload between stat and rename.
It renders the whole batch first,
publishes complete truth first, then complete packages; no existing output is
replaced, including a destination created concurrently. Ordinary failures remove
staged data and roll back this invocation's publication only. Cleanup opens
directories with `O_NOFOLLOW`, binds their descriptors to the recorded owned
type/device/inode before recursive traversal, and traverses relative to those
descriptors. It never recursively deletes a re-resolved pathname. Uncertain
ownership or concurrent changes preserve residue; final `rmdir` cannot delete
a replacement containing another writer's files. Unowned collisions are never
unlinked, and unexpected entries in job directories are preserved. Standalone
renderers use the same private job design for document publication.

Two distinct directories cannot be renamed atomically as one transaction.
A process kill or power loss can therefore leave private staging data or an
orphan **complete truth directory** before package publication. No partial package
batch is published. Recovery must inspect and remove only the interrupted job's
directories before using fresh outputs; this command does not guess ownership or
overwrite leftovers. This is exception-safe publication, not crash durability.

## Integration requirements

- The builtin CLI registers `cre_brain.evals.commands.register_cli(app)` only
  when `create_app` is called without an explicit plugin fixture;
  it lazily loads only its own checkout's `evals/generator`, without changing
  `sys.path` or inspecting a user's working directory. Importing CLI help does
  not load ReportLab or the fixture generator.
- Existing `reportlab==4.4.4` is a dev dependency and documents extra, not a core
  runtime dependency. A deployment running fixture generation needs that extra.
- The current wheel packages only `src/cre_brain`. Standalone wheel distribution
  of the public generator needs a coordinator-approved packaging change. Until
  then, a wheel without the public source directory fails closed with a source
  checkout requirement; the source/editable CLI is supported.
- Future harness/scorer work must enforce package-only mounting and consume this
  new public schema. This task does not read or adapt to any existing gold files.
- Calibration belongs to T050; broader synthetic report/lease renderers are
  outside T036. Owner review and the `protected-change` milestone label still
  apply to protected generator implementation.

Focused checks (no live models, services, integrations or private evals):

```bash
uv run pytest tests/evals -q --basetemp=.cache/pytest-t036
uv run ruff check evals/generator tests/evals src/cre_brain/evals
uv run ruff format --check evals/generator tests/evals src/cre_brain/evals
uv run mypy --strict src evals/generator
```
