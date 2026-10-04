# EVALS: how we know the analyst is good

> The product is an autonomous CRE acquisition analyst, "the Devin of real estate". Evals are its loss function. They are built **before** the agent, in milestone M2.

## 1. Principles
- **Deterministic checks first.** LLM judges come second and are only used once calibrated. Pairwise comparison is used only for prose quality.
- **Real data gates decisions; synthetic data trains and diagnoses.**
- **Protected.** After M2, `evals/**` is hash-checked in CI, owned by CODEOWNERS, and never edited by the learning loop.
- **Split by deal lineage, not by document chunk.** Related properties, sponsors, templates and generated ancestors all stay in the same split.

## 2. Eval sets

| Set | Source | Size (initial target) | Used for |
|---|---|---|---|
| **A. Synthetic deals** | `evals/generator/`: a latent deal is rendered into a rent roll (3 layouts: Yardi-like, RealPage-like, broker-custom; XLSX/CSV), a T-12 XLSX, an OM PDF and lease PDFs. Ground truth comes from code. | 2,000 per cycle, resampled | Optimization fixtures; defect recall |
| **B. Defects** | `evals/defects/`: about 30 types × 5 magnitudes, plus 20% clean controls (list below) | Mixed into A | DD and extraction recall/precision |
| **C. CMBS gold pairs** | CMBS 424B2 Annex A-1 (numbers) + A-3 (narrative) + EX-102 monthly performance (outcomes), multifamily only | ≥200 loans (≥5 offline fixtures in the repo) | Extraction accuracy on real documents; UW realism; risk-score AUROC against later DSCR/NOI and delinquency |
| **D. Real operating statements** | 8-K Rule 3-14 statements (apartment acquisitions by REITs) | ≥50 | T-12 normalization on real formats |
| **E. Calibration priors** | Cook County commercial valuation (rents, vacancy, expenses, cap rates for 7+ unit apartments), ACS, HUD FMR, FRED, BLS | n/a | Generator calibration; assumption ranges |
| **F. Adversarial** | Hidden or white text injection in OMs, instructions in lease exhibits, contradictory documents, missing documents, out-of-buy-box deals | 60 | Safety: 100% required on critical items |
| **G. Task requests** | Varied user requests ("just abstract leases", "screen + LOI at 6.25% cap", "compare deals 1–3"), each with an expected deliverable plan | 100 | Task-driven planning accuracy |
| **H. Question handling** | Scenarios that require a question; expected question, sensible default and correct revision after the answer | 60 | Ask-and-continue protocol |
| **I. Real deals (later)** | Owner and customer deals via `inbox/` + corrections (DAgger) | Grows over time | The true gate once available; shadow runs |

**Defect list (B):**
1. rent roll total ≠ GPR
2. expired leases counted as occupied
3. duplicate units
4. swapped unit IDs with the same totals
5. concessions hidden in other income
6. a pro forma that omits reserves
7. management fee missing
8. tax reassessment on sale ignored
9. insurance understated vs. market
10. T-12 months missing
11. year-to-date figure annualized as if it were a full year
12. a one-time item in NOI
13. utility reimbursement double-counted
14. a down unit counted as leased
15. a model unit counted as leased
16. bad debt omitted
17. loss-to-lease misstated
18. rent growth unsupported vs. comps
19. exit cap below going-in cap in a rising-rate setting
20. DSCR below lender minimum
21. a rollover cliff
22. a below-market lease option
23. a lease amendment overriding the base lease
24. an estoppel conflicting with the lease
25. an environmental REC in the Phase I
26. a PCA immediate-repair item
27. a zoning nonconformity
28. a title exception (easement or lien)
29. square footage mismatch
30. a stale appraisal date

## 3. Scorers (`evals/scorers/`)
- **Deterministic:**
  - field accuracy with typed tolerance
  - calc exactness vs. ground truth
  - defect recall and precision, severity-weighted
  - parity pass
  - provenance coverage
  - policy compliance
  - plan match (G)
  - question match + revision correctness (H)
- **Judge (binary rubric items):** memo sections present and correct, risks covered, reasoning consistent with numbers. Calibration:
  - ≥150 human labels per critical item before the judge may gate anything
  - report TPR/TNR and correct pass rates (Rogan-Gladen)
  - the judge must come from a different model family than the agent when a key is available
  - a 30-item anchor set checks for drift weekly
- **Backtest:** AUROC of the agent's risk score vs. a DSCR/LTV-only baseline, scored against EX-102 outcomes (delinquency, special servicing, NOI decline over 24–36 months).
- **Contamination guard:**
  - strip names, addresses and CUSIPs
  - perturb identifying figures
  - prefer vintages after the model's knowledge cutoff
  - report results with and without memorization risk

## 4. Splits
`train` (optimizer feedback), `dev` (keep/revert), `selection_holdout` (confirmation), and `sealed_test`.
- **Sealed test:** generated in CI from a seed stored as a CI secret (`EVAL_SEALED_SEED`), so it is never in the repo. It runs once per release, and each access is logged.
- 25% of the sealed test is refreshed each quarter.

## 5. Metrics and autonomy bars (initial; the owner can revise)

**North star: Clean Autonomous Task Rate.** The share of tasks that meet all of:
- completed
- zero critical errors
- question rate within bounds
- deliverables accepted without material edits (measured once humans review)

| Deliverable | Bar on sealed sets (2 consecutive releases) |
|---|---|
| Extraction | critical-field accuracy ≥99.5%; silent errors ≤0.2%; every checksum either ties or the deal escalates |
| SCREEN | decision agreement ≥95% on non-ambiguous cases; false-kill ≤5%; p50 latency ≤5 min |
| UW_MODEL | parity 100%; assumptions in-band ≥85%; value within ±5% of reference on ≥80% |
| IC_MEMO | provenance + entailment 100%; calibrated rubric pass ≥90% |
| DD_TRACKER | critical defect recall ≥95%; overall ≥85%; ≤1 false flag per deal |
| LOI | policy compliance 100%; key terms complete 100% |
| Task planning (G) | correct deliverable plan ≥95% |
| Questions (H) | right question asked ≥90%; correct revision after answer 100% |
| Adversarial (F) | 100% on critical items |
| Cost / latency | tracked and reported for every task; budgets in `config/budget.yaml` |

Bars measured on synthetic data alone are **necessary, not sufficient**. Real-deal shadow evidence is added as data arrives.

## 6. Running evals
- `make eval SUITE=<name>` runs inspect-ai tasks. Logs go to `logs/evals/`. A summary is written to `evals/reports/<date>.md`.
- In CI, without keys, the FakeRunner transcripts plus deterministic scorers run, which proves the plumbing works.
- With keys, live suites run nightly within budget.
