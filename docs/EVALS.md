# EVALS: how we know the analyst is good

> The product is an autonomous CRE acquisition analyst, "the Devin of real estate". Evals are its loss function.

## 1. Principles and physical separation
- **Deterministic checks come first.** LLM judges are advisory until they are calibrated on owner labels.
- **Real anchors gate decisions; synthetic data trains and diagnoses.** Scores on synthetic data measure agreement with our own generator. They are necessary, never sufficient.
- **Three locations:**

| Location | Contents | Who can read it |
|---|---|---|
| `evals/` in this repo (protected) | Generator, defect injector, scorers, suite definitions, public dev fixtures | Devin, CI |
| **Private repo `cre-ai-agent-evals-private`** | Selection-holdout and sealed-test seeds and configs, real-anchor gold answers, owner labels | CI (`EVALS_PRIVATE_TOKEN`) and the owner's scoring job only. **Never Devin, never analyst sessions.** |
| Analyst session container | **Only** the deal package (pre-parsed) and the brain | The analyst |

- **Blind scoring, enforced physically:**
  1. The analyst runs in a container with no repo mount and no access to `evals/` or the private repo.
  2. When it finishes, its deliverables are copied out.
  3. Only then does the scorer, a separate process, generate or fetch the truth and score the deliverables.
  4. `cre evals gen` writes packages and truth to **separate** directories, and the analyst container mounts only the package directory.
- **Split by deal lineage,** not by document chunk.
- **Reports** go to `reports/evals/` (not protected).

## 2. Eval sets

| Set | Source | Initial size | Role |
|---|---|---|---|
| **A. Synthetic deals** | `evals/generator/`: a latent deal is rendered into a rent roll (Yardi-like, RealPage-like and broker-custom layouts; XLSX/CSV), a T-12, an OM PDF, lease PDFs, **and third-party report summaries** (Phase I, PCA, title commitment, zoning letter, estoppels) | 500 per cycle (dev 100) | Optimization fixtures, diagnostics |
| **B. Defects** | 30 types (below) × 3 magnitudes, plus 20% clean controls | Mixed into A | DD and extraction recall/precision |
| **C. CMBS anchors** | EX-102 asset-level data **at securitization** (NOI, NCF, occupancy, DSCR, value, units) is the truth for the property's securitization underwriting. Annex A-1 tables and A-3 narratives are real document fixtures. Later EX-102 months provide outcomes. | ≥100 multifamily loans | Real-document extraction; risk ranking vs. outcomes |
| **D. Real operating statements** | 8-K Rule 3-14 statements (revenue and *certain* operating expenses; they exclude some costs by rule). Filings became rarer after the 2020 amendments | ≥20 (whatever exists) | Real-format T-12 normalization |
| **E. Calibration priors** | Cook County commercial valuation data, ACS, HUD FMR, FRED, BLS | n/a | Generator calibration; assumption ranges |
| **F. Adversarial** | Injection in OMs (hidden text, metadata, exhibits), contradictory documents, missing documents, out-of-box deals, malicious web pages for `browse` | 60 | Safety: 100% on critical items |
| **G. Task requests** | Varied user requests with the expected deliverable plan | 100 | Planning accuracy |
| **H. Question handling** | Scenarios with the expected question, an acceptable default, and the correct revision after the answer | 60 | Ask-and-continue |
| **I. Owner labels and real deals (when available)** | Owner-labelled outputs; owner and customer deals via `inbox/` + corrections | Grows | **The true gate**; judge calibration |

**Honest limits (do not hide these):**
- Annex A-1 is **lender** underwriting (NCF), not an acquisition package. It anchors extraction and realism, not purchase decisions.
- Anonymizing by perturbing numbers destroys "real numbers". So anonymize names, addresses and IDs only, and accept the memorization risk. Report results with and without the vintages most likely to have been memorized.
- Public data has **no property-level rent comps**. Comp-selection logic is evaluated on synthetic comp sets.

**Defect list (B):**
1. rent roll total ≠ GPR
2. expired leases counted as occupied
3. duplicate units
4. swapped unit IDs with the same totals
5. concessions hidden in other income
6. a pro forma that omits reserves
7. missing management fee
8. tax reassessment ignored
9. insurance understated
10. T-12 months missing
11. year-to-date figure annualized wrongly
12. a one-time item in NOI
13. utility reimbursement double-counted
14. a down unit counted as leased
15. a model unit counted as leased
16. bad debt omitted
17. loss-to-lease misstated
18. rent growth unsupported by the comps provided
19. exit cap below going-in cap in a rising-rate scenario
20. DSCR below lender minimum
21. a rollover cliff
22. a below-market lease option
23. a lease amendment overriding the base lease
24. an estoppel conflicting with the lease
25. a Phase I REC
26. a PCA immediate-repair item
27. a zoning nonconformity
28. a title exception
29. square-footage mismatch
30. a stale appraisal date

Defects 23–28 require the third-party renderers in set A.

## 3. Scorers
- **Deterministic:**
  - field accuracy with typed tolerance
  - calculation exactness vs. truth
  - defect recall and precision (severity-weighted)
  - parity
  - number provenance
  - policy compliance
  - plan match (G)
  - question match and revision correctness (H)
- **Judges (binary rubric items, advisory in v1):** a separate Codex session with an independent prompt. A judge may *gate* only after:
  - **≥150 owner labels per critical item** (T061 provides the labelling tool and queue)
  - TPR/TNR reported, with Rogan-Gladen-corrected pass rates
  - a 30-item anchor set for drift
- **Risk ranking:** `SCREEN` and `UW_MODEL` emit a numeric `risk_score` (a CalcResult combining DSCR cushion, occupancy, rollover, leverage and fragility margin). Score it by AUROC vs. a DSCR/LTV-only baseline against EX-102 outcomes: delinquency, special servicing, and an NOI decline of more than 10% within 24–36 months.

## 4. Splits
- `train`, `dev`, `selection_holdout` and `sealed_test`.
- `selection_holdout` and `sealed_test` seeds and configs live **only in the private repo**.
- The learning loop's confirmation step calls the **scoring service** (a CI job, or the owner's scoring worker) with the candidate release ID. It receives back **only pass/fail plus aggregate metrics**, never the cases.
- The sealed test runs once per release, and each access is logged. 25% is refreshed every quarter.

## 5. Metrics and bars (initial; the owner can revise)
**North star: Clean Autonomous Task Rate.** A task counts when it is completed with zero critical errors, the question rate is within bounds, and the deliverables are accepted without material edits. Acceptance is measured from owner labels and real-use edits once they exist.

| Deliverable | Bar | Measured on |
|---|---|---|
| Extraction | critical-field accuracy ≥99%; silent errors ≤0.5%; every checksum either ties or escalates | **C and D (real)** + A |
| SCREEN | buy-box inputs extracted correctly ≥98%; owner agreement ≥90% (once labels exist); p50 ≤10 min | C + A; I |
| UW_MODEL | parity 100%; Excel errors 0; NOI within ±3% of EX-102 securitization NOI on C (same basis); assumptions in-band ≥85% | **C** + A |
| IC_MEMO | number provenance 100%; required sections 100%; judge pass ≥90% (once calibrated) | A; I |
| DD_TRACKER | critical defect recall ≥95%; overall ≥85%; ≤1 false flag per deal | A/B |
| LOI | policy compliance 100%; key terms complete 100% | A |
| Risk ranking | AUROC ≥ baseline + 0.03 | C |
| Planning (G) | ≥95% | G |
| Questions (H) | right question ≥90%; correct revision 100% | H |
| Adversarial (F) | 100% on critical items | F |

## 6. Running evals
- `make eval SUITE=<name>` runs live analyst sessions (CodexRunner in repo-less containers) on the **public dev fixtures**, then runs the scorers. Reports go to `reports/evals/`.
- CI runs only FakeRunner plumbing tests plus scorer unit tests, and **no quality claims come from it**.
- Holdout and sealed scoring runs in CI or the owner's scoring job against the private repo.
- **Stress suite (M6):** concurrent tasks, slow SSE consumer, killed worker, dropped box.
