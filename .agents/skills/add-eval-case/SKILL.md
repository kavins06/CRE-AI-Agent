---
name: add-eval-case
description: Add an eval case or suite item (synthetic, defect, adversarial, task-request, question-handling) before evals are sealed, with deterministic ground truth.
---
# Add an eval case

**Allowed only before M2 is merged**, or later through a `protected-change` PR that the owner approves. The learning loop never adds eval cases.

1. Pick the set: A synthetic, B defect, C CMBS gold, D 3-14 statements, F adversarial, G task request, H question handling (see `docs/EVALS.md` §2).
2. Ground truth must come from code (`cre_brain.finance`, or the generator's latent deal), never from an LLM.
3. Assign the split by **deal lineage**: everything derived from the same latent deal or property goes in the same split.
4. Add the scorer mapping in `evals/scorers/` if it's a new field type.
5. Add a test proving the case is scorable: a correct answer scores 1, and a planted wrong answer scores 0.
6. Run `make eval SUITE=smoke`.
