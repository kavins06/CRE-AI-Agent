# DATA SOURCES

> The product is an autonomous CRE acquisition analyst. This file lists the data it can use without any owner deals.

Status legend:
- **[V]**: verified against primary docs during research on 2026-10-04.
- **[U]**: unverified. Confirm against the primary page before hard-coding; record the confirmation in PROGRESS.md.

Never hard-code credentials or personal contact details. All of them come from environment variables.

## Priority
| Use | Best sources |
|---|---|
| Real document fixtures and ground truth | CMBS Annex A-1/A-3 (424B2/FWP), 8-K Rule 3-14 statements |
| Outcomes for backtests | EDGAR ABS-EE EX-102 asset-level data; later Fannie/Freddie loan performance (licensed or permissioned) |
| Calibration priors | Cook County commercial valuation data, ACS, HUD FMR, FRED, BLS |

## 1. SEC EDGAR (public domain)
- **Fair access [V]:**
  - every request sends the header `User-Agent: $SEC_USER_AGENT`, a company name plus a contact address the owner provides
  - stay at **≤8 requests/second**; the SEC limit is 10/s per user
  - a request without a User-Agent gets HTTP 403 plus a temporary block
- **Index:** `https://www.sec.gov/Archives/edgar/full-index/{YYYY}/QTR{n}/form.idx`. Filter on `ABS-EE`, `424B2`, `FWP`, `8-K`.
- **Filing folder:** `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/index.json`.
- **Submissions:** `https://data.sec.gov/submissions/CIK{10-digit}.json`.
- **Full-text search [U, undocumented]:** `https://efts.sec.gov/LATEST/search-index?q=...&forms=...`, capped at about 10k hits.
- **ABS-EE EX-102 (CMBS asset-level XML, Reg AB II, Nov 2016 onward):** one `<assets>` element per loan per month.
  - Expected fields, **[U]** for exact names and casing (check against the SEC CMBS technical specification/XSD): `propertyTypeCode` (MF = multifamily), `unitsBedsRoomsNumber`, `valuationSecuritizationAmount`, `netOperatingIncomeSecuritizationAmount`, `mostRecentNetOperatingIncomeAmount`, DSCR at securitization and most recent, physical occupancy, `paymentStatusLoanCode`, special servicer transfer date, modification and loss fields.
  - Agency K-deals are **not** in EDGAR.
- **424B2 / FWP Annex A-1:** per-property units, appraised value and date, occupancy, historical and TTM NOI, underwritten revenue/expenses/NOI/NCF, DSCR, debt yield, LTV.
  - **Annex A-3:** narrative of the top loans.
  - Format is HTML or PDF.
  - Discover them with full-text search for "Annex A-1".
- **8-K / 8-K/A Rule 3-14 statements:** "Statement of Revenues and Certain Operating Expenses" for acquired apartment properties. These are audited, T-12-like statements.
- **Reference parsers to read, not vendor:** github.com/pgoldtho/visulate-abs and github.com/jgaudani/cmbs-radar.

## 2. Market and macro APIs
| Source | Endpoint | Key env var | Limits | Terms |
|---|---|---|---|---|
| FRED [V] | `https://api.stlouisfed.org/fred/series/observations?series_id=…&api_key=…&file_type=json` | `FRED_API_KEY` | ~120 req/min [U] | Most series are public domain; some third-party series are copyrighted |
| Census ACS 5-yr [V] | `https://api.census.gov/data/{year}/acs/acs5?get=…&for=…&in=…&key=…` | `CENSUS_API_KEY` | 50 variables/call; 500/day without a key | Public domain; attribution required |
| HUD FMR [V] | `https://www.huduser.gov/hudapi/public/fmr/{listStates,statedata/{ST},data/{entityid}}` | `HUD_API_TOKEN` (Bearer) | ~60 req/min [U] | Public domain |
| BLS v2 [V] | `POST https://api.bls.gov/publicAPI/v2/timeseries/data/` | `BLS_API_KEY` | 500 queries/day with a key | Public domain |

**Useful series and variables:**
- FRED: `DGS5`, `DGS7`, `DGS10`, `SOFR`, `CPIAUCSL`, `RRVRUSQ156N`
- ACS: `B25064_001E` median gross rent, `B25031` rent by bedrooms, `B25004_002E` for-rent vacant, `B25003_003E` renter-occupied, `B19013_001E` median household income
- BLS: `CUUR0000SEHA` rent of primary residence

## 3. County open data (Socrata; app token optional via `SOCRATA_APP_TOKEN`)
- **Cook County [U for dataset IDs]:** `https://datacatalog.cookcountyil.gov/resource/csik-bsws.json` (commercial valuation, 2021 onward: apartment rents, vacancy, expenses, NOI, cap rate); parcel sales `wvhk-k5uv`.
- **NYC:** ACRIS master `bnx9-e6tj`, legals `8h5j-fqxa`; PLUTO `64uk-42ks` (building classes C/D are apartments).
- **LA County:** assessor parcel data via the ArcGIS Hub API. Assessed value is not market value under Prop 13; use it for distributions only.

## 4. Licensed and permissioned (commercial licences are acceptable to the owner)
Each sits behind its connector interface. v1 ships stubs plus contract tests.
- **Data:** CoStar, Yardi Matrix, Trepp (CMBS loan data), Reducto (document extraction), Microsoft Graph Excel (real Excel recalculation).
- **Freddie Mac MLPD and K-deal disclosure, Fannie Mae Multifamily Loan Performance Data and DUS Disclose:**
  - registration is required
  - Freddie MLPD terms limit use to non-commercial / limited use, so **obtain commercial permission before using it in the product**
  - downloads are manual, with checksums recorded; no login automation

## 5. Do not use
- Scraped broker OMs from Crexi or LoopNet. Their terms forbid scraping and the content is copyrighted. Use them only to study layouts by hand, then render synthetic look-alikes.
- A.CRE models in the repo. They are copyrighted reference material only.
- ii-agent's bundled XLSX/DOCX/PDF/PPTX skills. They are proprietary.
