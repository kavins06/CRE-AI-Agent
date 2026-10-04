---
name: add-eval-case
description: Add an eval case or suite item (synthetic, defect, adversarial, task-request, question-handling) before evals are sealed, with deterministic ground truth.
---
# Add an eval case

`evals/` is a protected path, so changes reach `main` only through an owner-labelled PR. The learning loop never adds eval cases. **Holdout and sealed cases are never written here.** They live in the owner's private repo.

1. Pick the set: A synthetic, B defect, C CMBS gold, D 3-14 statements, F adversarial, G task request, H question handling (see `docs/EVALS.md` §2).
2. Ground truth must come from code (`cre_brain.finance`, or the generator's latent deal), never from an LLM.
3. Public cases go in `train`/`dev` only, assigned by **deal lineage**. Packages and truth are written to separate directories.
4. Add the scorer mapping in `evals/scorers/` if it's a new field type.
5. Add a test proving the case is scorable: a correct answer scores 1, and a planted wrong answer scores 0.
6. Run `make eval SUITE=smoke`.
