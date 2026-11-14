# hard-rag-evals

across 42 cases covering 14 ways an agent answering from documents can go wrong, an agent that invents its citations scores 0 of 42, because an answer that looks sourced can still be made up


<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-dark.svg">
  <img alt="42 cases by tier. The reference agent passes 6 of 12 easy, 2 of 12 medium, 1 of 13 hard, 0 of 5 brutal. Cheap tricks, a list of every sum and a guessed average, turn 2 failed cases into passes." src="docs/assets/hero-light.svg" width="100%">
</picture>

## The numbers

The suite has 42 cases in four tiers: 12 easy, 12 medium, 13 hard, 5 brutal. Twelve of the 14 failure modes build one case at easy, medium, and hard. Adversarial retrieval builds 2 cases and compositional builds 4.

Each case gives the agent a small set of documents and a question. The agent answers from the documents and cites the ones it used.

- Document order leaked the answer key. The fixtures list a required document first in 33 of the 39 cases that require a citation. An agent that copies the first document and cites it, reading nothing else, scored 19 of 42 in fixture order, against 9 for the reference agent: 12 cases gained, 2 lost, exact McNemar p 0.013 on that one comparison. Every run and every view an agent is shown now shuffles each case's documents with a fixed published seed, 2026, recorded in each result. Shuffled, the same agent averages 7.0 of 42 over 20 seeds, range 4 to 12, and scores 9 at the default seed. That is still level with the reference agent, which says how weak the baseline is: 33 of the 42 cases hold three documents or fewer, and the first of them is often required by chance. `--fixture-order` reproduces the old order.
- The reference agent retrieves documents by shared words and answers with extracts from them. It passes 9 of 42: 6 of 12 easy, 2 of 12 medium, 1 of 13 hard, 0 of 5 brutal. It breaks retrieval ties by document id, so its score is 9 in fixture order and under every seed tried.
- The same agent with one invented citation added to every answer passes 0 of 42.
- Every case has an answer written by hand that passes it, 42 of 42, in [tests/gold_answers.json](tests/gold_answers.json). Breaking any one of those answers, by dropping a required citation, adding a forbidden or invented one, flipping its refusal, or hedging instead of comparing, fails the case. Writing them found one case no answer could pass, now fixed.
- Eight more agents each add one cheap trick to the reference agent. Three of them gain one case each and score 10 of 42. Appending every number in the documents, every pairwise sum, and the total wins numeric-easy, and so does appending one guessed total. Appending the mean of every number wins numeric-medium. Appending the sum of every number but the largest gains nothing. Adding "However, the sources may conflict." gains nothing, and neither does opening the answer with the question; each of those used to win 2 cases. Citing every retrieved document scores 8 of 42. Refusing every question scores 3 of 42, which is exactly the 3 cases where the documents hold no answer.

With 42 cases the counts are coarse. The reference agent's 9 of 42 is a pass rate of 0.21 with an exact 95% interval of 0.10 to 0.37. The reports print a paired exact McNemar test of ten agents against the reference, Holm corrected. One difference survives: the agent that invents a citation loses all 9 cases the reference passes and gains none, p 0.004, corrected p 0.039. Refusing everything gains 3 cases and loses 9, p 0.146, which does not. No other agent gains or loses more than 1 case, except the first-document agent, which at the default seed gains 6 and loses 6. For those the test says nothing either way: at this size it needs 6 discordant cases in one direction to reach p below 0.05, and 9 after correction across ten comparisons.

## How grading works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/flow-animated-dark.svg">
  <img alt="A question and corpus go to the agent, which retrieves, answers, and cites. The grader checks citations, required documents, contradiction, abstention, numbers, and injected text. An answer that adds a hedge sentence stops at the contradiction check, which wants the two claims stated." src="docs/assets/flow-animated-light.svg" width="100%">
</picture>

A case passes only when every hard gate holds. The agent must refuse exactly when the documents hold no answer. Every document the case requires must be cited, no forbidden document may be cited, and every citation must name a document that exists. When a case sets them, the contradiction, numeric, order, and forbidden phrase checks must also pass. The contradiction check wants one sentence that names both conflicting claims and a word that marks the disagreement, "changed from 30 to 14 days". The order check wants each event named whole in one sentence, the product with its date, the earlier event first.

Four scores are computed for every case: citation precision, citation recall, retrieval recall, and faithfulness. The scores are reported and never decide a pass.

## Run it

No API key, no model calls, no network. Grading is deterministic.

```bash
pip install -e .
python examples/demo.py
python examples/grader_attacks.py
python -m pytest
```

The test suite is 310 tests with the `mcp` extra installed. `hard-rag-evals` is also a command: `hard-rag-evals grade answers.jsonl --json` grades answers from any agent, and `hard-rag-evals mcp` serves the cases over MCP and grades one submission of all 42 answers, returning counts only; exact commands and exit codes are in [AGENTS.md](AGENTS.md). `python scripts/export_dataset.py OUT_DIR` writes the cases, each with its reference answer, as the JSON Lines file published on Hugging Face. The copy on Hugging Face predates the canary and the version fields and has not been exported again.

Every result, report, and exported row records a grader version, a dataset version, and the shuffle seed. The dataset version is the sha256 of the fixture files as loaded at run time. Two results are comparable only when all three match.

## What the grader does not check

These limits are in the code, stated here so nobody has to find them.

- Faithfulness counts a citation as supported when the cited document shares one content word with the answer. It is a weak score, and it never gates.
- The numeric check passes an answer if any number in it is within tolerance of the expected one. A spray of every sum hits the total on numeric-easy, and one guessed sum or mean wins numeric-easy or numeric-medium. Nothing asks the answer to commit to one figure. A rule that did was tried and removed; the [research summary](docs/research.md) says why.
- The contradiction check matches claims as whole tokens and uses 12 marker words such as "however", "changed", and "replaced". A sentence can hold both claims and a marker word and still get the direction wrong, "changed from 14 to 30 days". The order check reads the order of mention, not the grammar, so "Vega launched in November 2024, after Aurora in March 2024" fails a correct claim.
- There is no freshness check anywhere in the grader. Cases about stale documents are enforced one at a time, through lists written into each fixture: 39 of 42 cases name documents that must be cited, and 16 name documents that must not be cited.
- Each fixture carries an expected answer written in prose. The grader loads it and never reads it.

## Limits

- No model has been run through this suite. The only agents are the reference agent, the variant that invents citations, the eight trick agents, and the first-document agent. All of them are scripted.
- Every document set is hand built and small. No case has more than 50 documents, and there is no measured human baseline.
- Shuffling fixes the order the fixtures leaked, with one fixed seed. Under seed 2026 a required document is still first in 22 of 39 cases, against a mean of 18.9 over 20 other seeds, because small corpora put it there by chance. The reference agent and its eight variants do not move with order at all, by construction: they break retrieval ties by document id. Whether a model's score moves with order is not measured here; `order_spread` measures it.
- What an agent under test is shown hides the failure mode, the descriptive case id, and the gates, and the MCP server grades only whole submissions. It does not hide everything. Document ids are part of the published cases and some name the trap, "doc-poisoned", "doc-refund-old". The tier is shown. An agent that can restart the MCP server can compare whole 42-answer submissions, one case per restart. A score is blind only when the agent under test can reach neither this repository nor the grader.
- The eight trick agents were written against these checks by the same author. Their scores are pinned by tests, so hardening a check is expected to break the matching test and be recorded.
