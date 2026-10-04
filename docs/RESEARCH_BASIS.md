# Research basis for the autonomous CRE acquisition analyst

Research date: October 3, 2026 (America/New_York). Decision: how to build an analyst that learns from the owner's expertise, supplied deals, public sources, and its own evaluated practice.

This is targeted primary-source research, not a systematic literature review or a replication. The mechanisms below have precedents; their combination for autonomous CRE acquisitions remains a design hypothesis. No finding here establishes a claim to be the first such product. Research papers, technical reports, software projects, vendor descriptions, and book catalog records have different evidentiary weight.

The owner clarified that meaningful expert involvement is available. The earlier review's ten-hour weekly assumption is superseded. The end goal remains full analyst autonomy within a defined acquisition mandate, with an increasingly automated learning process.

## What the evidence supports

| Claim | Evidence and status | Design consequence | Limit and confidence |
|---|---|---|---|
| C1. Internet material can help train agents when connected to tasks and feedback. | MineDojo [R1] reports internet-derived knowledge, a simulator, and a learned reward; VPT [R2] reports using labeled examples to extract training signal from unlabeled videos. Attributed research results. | Build collection, practice, and evaluation together. | High confidence in the reported mechanism; transfer to CRE is unproven. Web text alone does not supply investment-outcome labels. |
| C2. An agent can accumulate capabilities without changing foundation-model weights. | Voyager [R3] uses a curriculum, executable skill library, and iterative feedback. GEPA [R4] optimizes prompts. | Make external memory and tested skills the first learning substrate. | The papers support bounded tasks, not indefinite autonomous improvement in any domain. |
| C3. Automated improvement is strongest where candidates can be checked independently. | AlphaGeometry [R6] trains on machine-generated proofs; AlphaEvolve [R7] optimizes programs against evaluators. | Automate finance, extraction, and policy exercises with explicit expected outcomes. | Market forecasts and investment judgments lack an equivalent complete formal checker. |
| C4. Expert demonstrations should include the agent's actual mistakes. | DAgger [R8], especially section 3, aggregates expert labels on states visited by the learner. | Capture your corrections to agent attempts, not only ideal finished memos. | This is a DAgger-inspired workflow, not a claim that its theoretical guarantees transfer to LLM agents. |
| C5. Generated examples can improve weights, but filtering and ground truth matter. | STaR [R9] uses known answers and filtered rationales; Self-Instruct [R10] generates and filters instructions before fine-tuning. | Add supervised fine-tuning as an optional, evaluated track. | Correct final answers do not automatically validate every explanation or intermediate step. |
| C6. Research automation can propose useful hypotheses while still needing external validation. | Co-Scientist [R11] reports generation, critique, evolution, and selected biomedical validation. | Separate proposed lessons from established knowledge; test what can be tested. | Authors identify literature-access, source-quality, and evaluation limitations. |
| C7. Recursively generated training material can degrade learning. | Shumailov et al. [R12] study model collapse in recursive generative training. | Retain real evidence, track generated lineage, and test rare cases. | This is not evidence that all synthetic data, prompt edits, or retrieval cause model collapse. |
| C8. Experience, world models, and different memory types deserve separate treatment. | Sutton and Barto [B1] cover learning/planning and model error; Laird's publisher description [B2] documents Soar's integrated architecture and memories. | Separate knowledge, case memory, reusable procedures, and practice models. | Architecture is an informed synthesis, not a requirement to implement Soar or tabular RL. |

## Primary research and implemented precedents

### R1. MineDojo — internet knowledge plus an environment

**Linxi Fan et al., “MineDojo: Building Open-Ended Embodied Agents with Internet-Scale Knowledge,” NeurIPS 2022.** [Paper](https://arxiv.org/abs/2206.08853) · [Full text](https://arxiv.org/html/2206.08853).

Inspected abstract, sections 2–5, and relevant dataset/evaluation passages. The authors combine Minecraft tasks with videos, wiki pages, and forum discussions. MineCLIP learns video/text alignment and supplies a reward for policy learning. Some goals are programmatically checkable; others use learned evaluation.

**Borrow:** collect knowledge in relation to an executable curriculum, rather than building a document store with no learning objective. Pair a CRE source library with a deal-practice environment.

**Do not infer:** that Internet sources accurately label acquisition decisions, or that a learned judge becomes an independent financial truth source. Minecraft supplies repeatable interaction and feedback that CRE only partly offers.

### R2. Video PreTraining — small labeled seed, larger unlabeled corpus

**Bowen Baker et al., “Video PreTraining (VPT): Learning to Act by Watching Unlabeled Online Videos,” 2022.** [Author manuscript](https://arxiv.org/abs/2206.11795).

Scope inspected: abstract only. VPT trains an inverse-dynamics model on labeled data, uses it to label online videos, then trains a behavioral prior that can be further adapted.

**Borrow:** expert seed examples can help make a larger corpus useful. For CRE, labels might include document type, cited financial facts, calculation steps, or issue categories.

**Limit:** inferring action labels from game frames is not equivalent to inferring the correctness of an investment decision from a published memo. Treat this as a candidate approach to bootstrapping datasets, not proof of CRE transfer.

### R3. Voyager — curriculum and reusable skills

**Guanzhi Wang et al., “Voyager: An Open-Ended Embodied Agent with Large Language Models,” 2023.** [Project and paper](https://voyager.minedojo.org/) · [Author manuscript](https://arxiv.org/abs/2305.16291).

Inspected the paper's method, skill-library, self-verification, and limitations sections. Voyager uses a black-box GPT-4 model, an automatic curriculum, executable skill memory, and feedback. Model weights are not updated. Its success critic is itself model-based in part; the paper reports critic failures and impossible proposed tasks.

**Borrow:** a competency graph, choosing the next useful practice task, tested skill reuse, and learning from execution errors.

**Limit:** use stronger deterministic checks where CRE permits them; do not inherit the model critic as the sole authority.

### R4. GEPA — measured prompt evolution

**Lakshya A. Agrawal et al., “GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning,” 2025, revised 2026; author record identifies ICLR 2026 acceptance.** [Full text, v2](https://arxiv.org/html/2507.19457v2).

Inspected the method, selection procedure, benchmark description, and cost passages. The paper reports up to 35 times fewer rollouts than its GRPO comparison. It explicitly uses a validation set for candidate selection.

**Borrow:** propose mutations from failure feedback, compare candidates under a fixed budget, retain useful alternatives, and measure generalization.

**Limit:** the published ratio is not a forecast of CRE cost or accuracy. Validation used for selection is not a sealed final test. Include reflection and evaluation in cost accounting.

### R5. ACE — an evolving playbook

**Qizheng Zhang et al., “Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models,” 2025, revised 2026; author record identifies ICLR 2026.** [Full text, v3](https://arxiv.org/html/2510.04618v3).

Inspected sections 3–5, including domain tasks and limitations. ACE uses generation, reflection, and incremental curation rather than repeatedly replacing the whole context. Finance tasks include FiNER/XBRL entity labeling and Formula numerical reasoning. The paper explicitly warns that poor reflection can produce harmful context.

**Borrow:** small, versioned additions and corrections to a playbook, with evidence and retirement rules.

**Limit:** finance benchmarks here are not end-to-end CRE investment decisions. More accumulated context is not always better. Compare ACE-style memory against simpler retrieval and prompt baselines.

### R6. AlphaGeometry — synthetic training with a formal checker

**Trieu H. Trinh et al., “Solving olympiad geometry without human demonstrations,” Nature 625, 476–482 (2024).** [Published article](https://www.nature.com/articles/s41586-023-06747-5).

Inspected abstract, main method, and synthetic-data discussion. The system combines a neural model trained on synthetic proofs with symbolic deduction. The reported result is 25 solved problems out of a 30-problem olympiad geometry set.

**Borrow:** generate a known underlying financial situation first, then render documents and derive checkable answers. A financial calculation or planted inconsistency can have an exact oracle.

**Limit:** a formally valid proof differs from a market forecast. A simulator cannot prove the real-world probability of its own assumptions.

### R7. AlphaEvolve — automated experimentation against evaluators

**Google DeepMind, “AlphaEvolve: A coding agent for scientific and algorithmic discovery,” technical report (2025).** [Official announcement and linked report](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/).

Inspected the linked report's introduction, program evaluation, and limitations. It combines generated program candidates, evaluation, and evolutionary search. The report explicitly limits its approach where experiments require manual evaluation.

**Borrow:** isolated experiments, evaluator-owned scoring, candidate archives, reproducible comparisons, and automatic rejection of regressions.

**Limit:** evidence comes from a developer-authored technical report; it is not independent confirmation of every operational claim. The key mechanism depends on the evaluator being meaningful and protected.

### R8. DAgger — expert correction where the learner goes wrong

**Stéphane Ross, Geoffrey Gordon, and Drew Bagnell, “A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning,” AISTATS/PMLR 15:627–635 (2011).** [Proceedings and paper](https://proceedings.mlr.press/v15/ross11a.html).

Inspected abstract and section 3, Dataset Aggregation. The learner visits states under its own policy; expert labels on those states are aggregated into further training.

**Borrow:** let the agent attempt real workflows and ask you to correct consequential errors, missing evidence, and next actions. Save the actual state and correction, not only the final polished output.

**Limit:** expert consistency and task representation still matter. A complex LLM workflow does not automatically satisfy the paper's assumptions.

### R9. STaR — optional weight learning from verified examples

**Eric Zelikman, Yuhuai Wu, Jesse Mu, and Noah D. Goodman, “STaR: Bootstrapping Reasoning With Reasoning,” 2022.** [Paper](https://arxiv.org/abs/2203.14465) · [Full text](https://arxiv.org/html/2203.14465).

Inspected abstract, iterative method, and failure discussion. STaR generates rationales, uses known correct answers to filter or regenerate examples, and fine-tunes iteratively.

**Borrow:** supervised learning on successful, verified task records when a trainable model and sufficient suitable data exist.

**Limit:** do not treat a convincing explanation as verification. In CRE, train on observable decision records, calculations, citations, and reviewed justifications. This does not require access to a provider's private internal reasoning.

### R10. Self-Instruct — generating practice and training tasks

**Yizhong Wang et al., “Self-Instruct: Aligning Language Models with Self-Generated Instructions,” ACL 2023.** [Proceedings and paper](https://aclanthology.org/2023.acl-long.754/).

Inspected the published abstract and the paper's generation/filtering method. It creates instructions and examples, removes invalid/similar material, and fine-tunes on the remainder.

**Borrow:** propose varied exercises from a curriculum, deduplicate, and use explicit answer verification.

**Limit:** filtering fluency and similarity is insufficient for underwriting truth. Preserve real cases and independently checked answers rather than replacing the corpus with generated material.

### R11. Co-Scientist — literature-informed hypothesis generation

**Juraj Gottweis et al., “Accelerating scientific discovery with Co-Scientist,” Nature, published May 19, 2026.** [Published article](https://www.nature.com/articles/s41586-026-10644-y) · [Earlier preprint lineage](https://arxiv.org/abs/2502.18864).

Inspected the published abstract, system description, validation discussion, and limitations. The system generates, critiques, and evolves hypotheses, with selected biomedical results checked experimentally. The paper identifies missing negative findings, restricted literature access, source-quality problems, and imperfect factuality.

**Borrow:** an automated research queue that forms testable lessons from literature, compares alternatives, and separates proposal from validation.

**Limit:** tournament scores and literature agreement do not replace experiments. For CRE, substitute reviewed case evidence, calculation tests, prospective comparison, and eventual outcomes as appropriate. Do not add multiple agents merely because this implementation used them; evaluate the need.

### R12. Recursive training failure — counterevidence to naive self-training

**Ilia Shumailov et al., “AI models collapse when trained on recursively generated data,” Nature 631, 755–759 (2024).** [Published article](https://www.nature.com/articles/s41586-024-07566-y).

Inspected abstract and main explanation of recursive training and tail loss.

**Borrow:** retain original data, preserve rare cases, identify synthetic lineage, and compare against an unchanged real test set.

**Limit:** the finding concerns the studied recursive training conditions. It does not establish that every use of synthetic tasks or every form of agent memory causes collapse.

### R13. FinRobot — adjacent financial-agent work

**Hongyang Yang et al., “FinRobot: An Open-Source AI Agent Platform for Financial Applications using Large Language Models,” 2024 whitepaper/preprint.** [Paper](https://arxiv.org/abs/2405.14767) · [Full text, v1](https://arxiv.org/html/2405.14767v1).

Inspected architecture, task examples, and evaluation/demo discussion. It describes a financial-agent platform and workflows; this is adjacent prior work, not evidence of autonomous CRE acquisition competence.

**Borrow:** inspect reusable financial tools and reporting patterns. Assess implementations before deciding to reuse them.

**Limit:** a platform demonstration is not independent validation of investment returns or reliable autonomous decision-making. This review did not reproduce the code or establish a comprehensive novelty landscape.

### R14. Karpathy autoresearch — an implementation pattern

**Andrej Karpathy, `autoresearch` software project.** [Author repository](https://github.com/karpathy/autoresearch) · [README inspected](https://raw.githubusercontent.com/karpathy/autoresearch/master/README.md).

The README describes an agent editing training code, running a fixed-duration experiment, and keeping/discarding changes based on validation bits per byte. It is software documentation, not a peer-reviewed demonstration of self-taught financial expertise.

**Borrow:** bounded experiments and a transparent experiment log. Our initial editable objects are prompts, skills, retrieval settings, and candidate tools; optional model-training experiments come later. Do not copy the language-model loss as an investment-quality metric.

## Books and how to use them

### B1. Sutton and Barto — learning, feedback, planning, model error

**Richard S. Sutton and Andrew G. Barto, Reinforcement Learning: An Introduction, second edition, MIT Press (2018).** [Publisher](https://mitpress.mit.edu/9780262039246/reinforcement-learning/) · [Authors' book page and public PDF](http://incompleteideas.net/book/the-book-2nd.html).

Inspected selected passages of the authors' full PDF: section 1.1 (learning through interaction), section 8.1 (models and planning), and section 8.3 (when the model is wrong). This was not a cover-to-cover reading. These passages support the distinction between collecting information, practicing in a modeled environment, and learning from external feedback.

**Application:** design explicit tasks, actions, feedback, and limits to the practice environment. Keep track of whether feedback comes from actual evidence or a simulator. A simulated reward should not silently become an investment-outcome label.

### B2. Laird — a built architecture for integrated learning and memory

**John E. Laird, The Soar Cognitive Architecture, MIT Press (2012; paperback 2019).** [Publisher](https://mitpress.mit.edu/9780262538534/the-soar-cognitive-architecture/) · [University project](https://soar.eecs.umich.edu/).

Inspected the publisher's description and the university project overview, not the book's full text. Soar is an implemented cognitive architecture, with integrated reasoning and learning and extensions including semantic and episodic memory.

**Application:** a strong further-reading reference for separating facts, experiences, and procedures. The proposed CRE architecture is an adaptation of that general distinction, not a verified implementation of Soar's mechanisms.

### B3. Linneman and Kirsch — the domain curriculum

**Peter Linneman and Bruce Kirsch, Real Estate Finance and Investments: Risks and Opportunities, edition 5.3 (2024).** [Authors' official textbook description](https://www.linnemanassociates.com/real-estate-finance-texbook).

Inspected the official description, which identifies the edition, investment-judgment emphasis, and associated Excel material. The full paid text and workbook contents were not inspected. The page distinguishes financial modeling from investment judgment.

**Application:** a candidate licensed curriculum anchor, alongside the owner's own conventions and current primary sources. Create source-linked lessons and independently checked exercises when the material is available under suitable usage rights. The book is not evidence that an autonomous analyst has already been built.

## Public-source starting points

These are verified discovery portals, not completed datasets or a completed training corpus:

- [Fannie Mae Multifamily Guide](https://mfguide.fanniemae.com/): lender requirements and underwriting topics. Rules are program-specific, versioned, and not universal equity-investment policy.
- [Freddie Mac Multifamily Guide and Forms](https://mf.freddiemac.com/lenders/guide): another primary lending source, with the same scope caution.
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces): filings and structured company facts. Loan-level ABS exhibits, property-level documents, and outcome matching require separate collection and verification; the company-facts API does not automatically provide a clean CRE backtest.
- [ALFRED](https://alfred.stlouisfed.org/): historical vintages of economic series, useful for limiting retrospective information leakage.
- Local assessor, recorder, planning/zoning, Census, BLS, and HUD sources are collection candidates to validate when a market and task are chosen; they were not individually inspected in this research pass.

Public availability does not establish training rights, completeness, accuracy, or authority over the owner's investment policy. Record permitted uses and original source lineage. Market material, textbooks, seller assertions, and verified financial facts must retain different statuses.

## Remaining uncertainty and next experiments

1. **Learning gain:** on the same held-out real tasks and total budget, compare a fixed baseline, retrieval only, expert revisions, GEPA, and incremental memory. Add components only when their benefit is measurable.
2. **Public-source yield:** build a small source-to-exercise pilot and measure correctness, useful coverage, duplication, and review effort. Do not equate pages collected with competence gained.
3. **Judgment transfer:** can lessons learned from one packet improve decisions on different properties, sponsors, templates, and market conditions? Use prospective cases where feasible.
4. **Evaluation fidelity:** can the evaluator catch failures planted to fool it, including correct totals with wrong meaning and plausible but unsupported assumptions?
5. **Weight training:** only after enough verified examples exist, compare fine-tuning a supported model against retrieval and prompt/skill learning. Access, data rights, compute, and capability gains determine the choice.
6. **Autonomy:** validate analyst authority and automatic release authority separately. None of these sources establishes a universal sample size or a universal safe operating domain for CRE.

These gaps should drive the project experiments. They are not reasons to abandon the autonomous endpoint.
