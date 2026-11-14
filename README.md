# hard-rag-evals

across 42 cases covering 14 ways an agent answering from documents can go wrong, an agent that invents its citations scores 0 of 42, because an answer that looks sourced can still be made up


<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-dark.svg">
  <img alt="42 cases by tier. The reference agent passes 6 of 12 easy, 2 of 12 medium, 1 of 13 hard, 0 of 5 brutal. Cheap tricks, a list of every sum and a guessed average, turn 2 failed cases into passes." src="docs/assets/hero-light.svg" width="100%">
</picture>

## The numbers

The suite has 42 cases in four tiers: 12 easy, 12 medium, 13 hard, 5 brutal. Twelve of the 14 failure modes build one case at easy, medium, and hard. Adversarial retrieval builds 2 cases and compositional builds 4.

Each case gives the agent a small set of documents and a question. The agent answers from the documents and cites the ones it used.

- The reference agent retrieves documents by shared words and answers with extracts from them. It passes 9 of 42: 6 of 12 easy, 2 of 12 medium, 1 of 13 hard, 0 of 5 brutal.
- The same agent with one invented citation added to every answer passes 0 of 42.
- Every case has an answer written by hand that passes it, 42 of 42, in [tests/gold_answers.json](tests/gold_answers.json). Breaking any one of those answers, by dropping a required citation, adding a forbidden or invented one, flipping its refusal, or hedging instead of comparing, fails the case. Writing them found one case no answer could pass, now fixed.
- Eight more agents each add one cheap trick to the reference agent. Three of them gain one case each and score 10 of 42. Appending every number in the documents, every pairwise sum, and the total wins numeric-easy, and so does appending one guessed total. Appending the mean of every number wins numeric-medium. Appending the sum of every number but the largest gains nothing. Adding "However, the sources may conflict." gains nothing, and neither does opening the answer with the question; each of those used to win 2 cases. Citing every retrieved document scores 8 of 42. Refusing every question scores 3 of 42, which is exactly the 3 cases where the documents hold no answer.

With 42 cases the counts are coarse. The reference agent's 9 of 42 is a pass rate of 0.21 with an exact 95% interval of 0.10 to 0.37. The reports also print a paired exact McNemar test of each trick agent against the reference. None is significant, and that is a null with no weight: at this size the test needs 6 discordant cases in one direction to reach p below 0.05, 9 after Holm correction across the eight agents, and no trick agent gains more than 1. The case counts above are the evidence; the test only shows how little 42 cases can separate.

## How grading works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/flow-animated-dark.svg">
  <img alt="A question and corpus go to the agent, which retrieves, answers, and cites. The grader checks citations, required documents, contradiction, abstention, numbers, and injected text. An answer that adds a hedge sentence stops at the contradiction check, which wants the two claims stated." src="docs/assets/flow-animated-light.svg" width="100%">
</picture>

A case passes only when every hard gate holds. The agent must refuse exactly when the documents hold no answer. Every document the case requires must be cited, no forbidden document may be cited, and every citation must name a document that exists. When a case sets them, the contradiction, numeric, order, and forbidden phrase checks must also pass. The numeric check reads amounts, a number with a currency sign, a scale word, or at least 1,000, and wants one within tolerance and none that is neither that nor quoted from the question or the documents. The contradiction check wants one sentence that names both conflicting claims and a word that marks the disagreement, "changed from 30 to 14 days". The order check wants each event named whole in one sentence, the product with its date, the earlier event first.

Four scores are computed for every case: citation precision, citation recall, retrieval recall, and faithfulness. The scores are reported and never decide a pass.

## Run it

No API key, no model calls, no network. Grading is deterministic.

```bash
pip install -e .
python examples/demo.py
python examples/grader_attacks.py
python -m pytest
```

The test suite is 251 tests with the `mcp` extra installed. `hard-rag-evals` is also a command: `hard-rag-evals grade answers.jsonl --json` grades answers from any agent, and `hard-rag-evals mcp` serves the cases and the grader over MCP; exact commands and exit codes are in [AGENTS.md](AGENTS.md). `python scripts/export_dataset.py OUT_DIR` writes the cases, each with its reference answer, as the JSON Lines file published on Hugging Face. The copy on Hugging Face predates the canary and the version fields and has not been exported again.

Every result, report, and exported row records a grader version and a dataset version, the sha256 of the fixture files. Two results are comparable only when both match.

## What the grader does not check

These limits are in the code, stated here so nobody has to find them.

- Faithfulness counts a citation as supported when the cited document shares one content word with the answer. It is a weak score, and it never gates.
- The numeric check reads only amounts: a number with a currency sign, a number with a scale word (thousand, million, billion, K, M, B), or a number of at least 1,000. Counts, list numbering, citation markers, and percentages are ignored. It passes when one amount is within tolerance and every other amount is in the question, a document, or a document's date. It reads figures, not sentences, so these wrong answers pass: "It was not $10 million", several guesses that all sit inside the tolerance, and a second guess written in words or without its scale word. These correct answers fail: an intermediate result written as an amount, "cover to 2026, extended to 2027", and a figure written in words.
- On numeric-easy a list of every number and sum still wins. The case has two inputs, so the list is the two inputs and their one sum, the same text as a correct answer that shows its working. No rule that reads the text can separate them. The rule bites where a list has to state sums the documents do not: on numeric-hard the list holds the expected $10 million and fails on $7.3, $8.9, and $13.1 million beside it.
- One guessed figure can be right by luck of the operation. Appending the sum of every number wins numeric-easy, and appending the mean wins numeric-medium. The check cannot tell a guess from a computation when the guess is the answer.
- The contradiction check matches claims as whole tokens and uses 12 marker words such as "however", "changed", and "replaced". A sentence can hold both claims and a marker word and still get the direction wrong, "changed from 14 to 30 days". The order check reads the order of mention, not the grammar, so "Vega launched in November 2024, after Aurora in March 2024" fails a correct claim.
- There is no freshness check anywhere in the grader. Cases about stale documents are enforced one at a time, through lists written into each fixture: 39 of 42 cases name documents that must be cited, and 16 name documents that must not be cited.
- Each fixture carries an expected answer written in prose. The grader loads it and never reads it.

## Limits

- No model has been run through this suite. The only agents are the reference agent, the variant that invents citations, and the eight trick agents. All of them are scripted.
- Every document set is hand built and small. No case has more than 50 documents, and there is no measured human baseline.
- The eight trick agents were written against these checks by the same author. Their scores are pinned by tests, so hardening a check is expected to break the matching test and be recorded.
