# hard-rag-evals

across 42 cases covering 14 ways an agent answering from documents can go wrong, an agent that invents its citations scores 0 of 42, because an answer that looks sourced can still be made up


<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-dark.svg">
  <img alt="42 cases by tier. The reference agent passes 7 of 12 easy, 2 of 12 medium, 1 of 13 hard, 0 of 5 brutal. Cheap tricks turn 3 failed cases into passes, including the sentence: However, the sources may conflict." src="docs/assets/hero-light.svg" width="100%">
</picture>

## The numbers

The suite has 42 cases in four tiers: 12 easy, 12 medium, 13 hard, 5 brutal. Twelve of the 14 failure modes build one case at easy, medium, and hard. Adversarial retrieval builds 2 cases and compositional builds 4.

Each case gives the agent a small set of documents and a question. The agent answers from the documents and cites the ones it used.

- The reference agent retrieves documents by shared words and answers with extracts from them. It passes 10 of 42: 7 of 12 easy, 2 of 12 medium, 1 of 13 hard, 0 of 5 brutal.
- The same agent with one invented citation added to every answer passes 0 of 42.
- Four more agents each add one cheap trick to the reference agent. Citing every retrieved document and adding the sentence "However, the sources may conflict." scores 11 of 42. Appending every number in the documents, every pairwise sum, and the total scores 11 of 42. Citing every retrieved document scores 9 of 42. Refusing every question scores 3 of 42, which is exactly the 3 cases where the documents hold no answer.

## How grading works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/flow-animated-dark.svg">
  <img alt="A question and corpus go to the agent, which retrieves, answers, and cites. The grader checks citations, required documents, contradiction, abstention, numbers, and injected text. A hedge sentence fools the contradiction check and a number spray fools the numeric check." src="docs/assets/flow-animated-light.svg" width="100%">
</picture>

A case passes only when every hard gate holds. The agent must refuse exactly when the documents hold no answer. Every document the case requires must be cited, no forbidden document may be cited, and every citation must name a document that exists. When a case sets them, the contradiction, numeric, order, and forbidden phrase checks must also pass.

Four scores are computed for every case: citation precision, citation recall, retrieval recall, and faithfulness. The scores are reported and never decide a pass.

## Run it

No API key, no model calls, no network. Grading is deterministic.

```bash
pip install -e .
python examples/demo.py
python examples/grader_attacks.py
python -m pytest
```

The test suite is 35 tests.

## What the grader does not check

These limits are in the code, stated here so nobody has to find them.

- Faithfulness counts a citation as supported when the cited document shares one content word with the answer. It is a weak score, and it never gates.
- The contradiction check needs both documents of a conflicting pair cited, then looks for any of 12 marker words in the answer, words such as "however", "changed", and "replaced". An answer that copies one of those words out of a document passes without comparing the two claims.
- There is no freshness check anywhere in the grader. Cases about stale documents are enforced one at a time, through lists written into each fixture: 39 of 42 cases name documents that must be cited, and 16 name documents that must not be cited.
- Each fixture carries an expected answer written in prose. The grader loads it and never reads it.

## Limits

- No model has been run through this suite. The only agents are the reference agent, the variant that invents citations, and the four trick agents. All of them are scripted.
- Every document set is hand built and small. No case has more than 50 documents, and there is no measured human baseline.
- The four trick agents were written against these checks by the same author. Their scores are pinned by tests, so hardening a check is expected to break the matching test and be recorded.
