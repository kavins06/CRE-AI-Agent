# Licensed public CRE reference library

`cre_brain.knowledge` is reference infrastructure, not model-weight training,
verified deal facts, calculations, tenant memory, or an evaluation corpus.
`catalog.json` in the installed package is the **single rights authority**.
The coordinator supplied 42 publisher/agency-reviewed records; identical works
and editions were consolidated into 34 resources: 17 `DOWNLOAD_ALLOWED` and
17 `REFERENCE_ONLY`. Aliases resolve to the same resource, without duplicate
ingestion. Different Geltner editions remain distinct. Publication-date strings
preserve year/month precision and issuance/revision distinctions from the research.
`verified_at` dates the supplied bibliographic/rights review, not a successful import.

## Rights and evidence boundary

- Public availability is not a reuse license. Only resources explicitly reviewed
  for commercial reuse in the United States have a download URL and exact URL
  allowlist. Government public-domain permission covers qualifying federal-authored
  text, **not** independent third-party standards, photographs, seals, logos, or
  endorsement. International rights are not established.
- Unknown rights, contractor/noncommercial content (including OpenStax's
  CC BY-NC-SA), books, ASTM, IREM, ULI and lender/servicer materials without
  ingestion rights remain bibliographic metadata and human-facing citations.
  No fetching, document ingestion, embedding or full-text indexing of these entries.
- PDF text extraction discards graphics and conservatively skips pages mentioning
  copyright, third-party permission/credits, or missing-children material.
  Skipped physical PDF page numbers are recorded. This is an additional safeguard,
  **not a legal clearance engine**. Source caveats still apply. Operators must
  review reused excerpts/third-party material and current law before redistribution.
- Every chunk has source ID/title/URL/license, physical 1-based PDF page,
  optional first-line section heading (heuristic, not a verified outline),
  download hash and UTC retrieval time. Images and table structure are not extracted;
  no OCR. Reference-only hits have no text, page, hash or invented retrieval date.
- Hits explicitly carry `global_public` scope and
  `public_reference_not_deal_fact` role. Their contents remain untrusted reference
  text, never tool instructions. Financial quantities still require stored
  `Fact`/`CalcResult` evidence and deterministic calculation. There is no promotion
  into canonical deal state, no local-document/URL import endpoint and no credentials.
- SEC, EDGAR, CMBS/EX-102, Annex and Rule 3-14 are disabled and absent. No private
  evaluation repositories, truth, customer deals, or tenant documents are read.

## Operator CLI (one existing `cre` CLI)

```sh
./init.sh
cre knowledge catalog
cre knowledge import mfuv-occ-cre-lending-2022          # disabled, no network/cache writes
cre knowledge import mfuv-occ-cre-lending-2022 --allow-download
cre knowledge search "DSCR net operating income" --limit 5 --max-chars 12000
```

PDF parsing uses only the security-reviewed `pypdf==6.19.0` pin. Installing other
versions does not bypass the parser's check. Bibliographic catalog/search works
without PDF extras. The importer defaults `off`; `ask` returns
`pending_confirmation` without blocking or fetching, and `on` is an explicit
operator choice. `--allow-download` is not an analyst-callable policy override.

`KnowledgeProvider.search(SearchRequest) -> SearchResult` is the typed public
retrieval seam for the future canonical T032 tool registry and T092 memory
aggregator. CLI and Python call the same implementation. Do not build another
catalog, inference engine, MCP registry, or memory authority: register
`knowledge_search` against this provider once T032 exists. Import must stay
operator-only until routed through the canonical policy toggle. Future firm/user
providers must be physically separate, authenticated/sanitized, and return
distinct scopes; this provider rejects firm/user scope or context fields.
There is no claim that unimplemented T032/T092 tasks are complete.

## Fetching, parsing and cache controls

- Only exact reviewed URLs, no arbitrary URL argument and no crawling. At most
  four requests (initial plus three redirects); every hop must be explicitly
  listed. HTTPS only, port 443, no URL credentials/query tokens/fragments or SEC.
- DNS resolves in a credential-free subprocess with a five-second maximum;
  **all** returned addresses must be globally routable. The TLS connection pins
  one validated address but checks the certificate against the original hostname.
  No second DNS resolution, proxies, environment auth, cookies, netrc, Referer,
  or caller-provided request headers.
- Maximum 25 MB, 30-second total download budget (configurable only downward/up
  to hard 60 seconds), PDF MIME and signature checks, no HTTP compression.
  Response-body checks apply even without Content-Length. Non-200 responses and
  challenge pages fail without activating cache content.
- Linux/POSIX text parser subprocess: credential-free environment, 768 MiB
  address-space cap, 30/35-second CPU soft/hard caps, 40-second wall budget,
  at most 1,000 pages, 80,000 characters/page, 3M characters/document and 10,000
  chunks. Corrupt/encrypted/non-text documents are refused, not silently treated
  as successful imports. It is resource-limited, not a container sandbox.
- Cache paths must be a dedicated external `public-knowledge` directory,
  outside **every Git checkout** and not inside deals/firms/evals/truth.
  No-follow directory-FD IO rejects traversal, symlinks, non-regular files and
  hardlinks. Files are mode 0600; created directories 0700. Writes are atomic,
  fsynced; a nonblocking per-resource process lock prevents competing imports.
  These controls do **not** isolate from another root/same-UID writer on a shared VM.
- Default root is `$XDG_DATA_HOME/cre-brain/public-knowledge`, or
  `~/.local/share/cre-brain/public-knowledge`. `--cache-dir` may select another
  dedicated external directory with that final name. `.gitignore` provides
  additional accidental-cache protection.
- Each version is `<root>/<resource-id>/<SHA256>/document.pdf`, `metadata.json`
  and `chunks.json`. Hashes of both raw artifact and parsed chunks are validated
  before retrieval. The cache manifest includes the catalog's hash. Changing
  catalog rights/metadata fails closed and requires cache review/rebuild.
- Unchanged downloads return the original artifact/citation, making imports
  idempotent. A changed PDF is stored as an inactive candidate and returns
  `changed_requires_review`; the previous active version remains intact.
  Only `--accept-change` after rights/content review activates a replacement;
  previous versions remain available for citation replay.
- Retrieval is deterministic bounded lexical ranking, not a live model/embedding
  service: up to 20 hits and 20,000 compact JSON characters, including citations
  and caveats. A very small budget may yield no hits instead of stripping rights
  or fabricating content. Unavailable/uncached sources provide cited metadata.
  Corrupt caches fail explicitly rather than returning unverified text.

## Retention and reproducibility

The public cache is local operator-owned working data, not versioned source,
release content or tenant storage. Approved active versions, inactive change
candidates and original source PDFs are retained until the operator removes
them; **no automatic deletion or legal hold is implemented**. Review stale
candidates and source rights/currentness periodically; budget storage before
imports. Preserve the exact referenced versions privately for any required
audit/replay period, then remove only this dedicated cache and its indexes,
copies/backups as appropriate. No customer data should ever enter this cache.
Catalog metadata and importer code alone are in Git. Downloaded PDFs, extracted
full text and cached pages must never be committed or redistributed wholesale.

Offline tests use small generated public/synthetic PDF fixtures, real parser
subprocesses, real cache IO and transport doubles. Actual import counts and source
failures are reported separately in `PROGRESS.md`; no mock or FakeRunner result
demonstrates analyst quality, current-law correctness or evaluation readiness.
