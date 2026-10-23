# hard-rag-evals

Evals for agents that answer from retrieved documents. 14 failure modes, 42 cases. A reference agent passes 10 of 42. Four agents built to game the grader turn 3 failed cases into passes, and this repo maps which checks fall and which hold.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-dark.svg">
  <img alt="42 cases by tier. The reference agent passes 7 of 12 easy, 2 of 12 medium, 1 of 13 hard, 0 of 5 brutal. Cheap tricks turn 3 failed cases into passes, including the sentence: However, the sources may conflict." src="docs/assets/hero-light.svg" width="100%">
</picture>

<sub>Four repos share one question: how can we trust what an agent hands back without a human checking it?<br>
[agent-harness](https://github.com/pdj555/agent-harness) · [agent-eval-harness](https://github.com/pdj555/agent-eval-harness) · [trajectory-to-training](https://github.com/pdj555/trajectory-to-training) · **hard-rag-evals**</sub>

## The findings

An answer from retrieved documents has to carry its own proof: real citations, the current fact over the stale one, a contradiction named instead of buried, and no answer at all when the documents hold nothing.

| Agent | Easy | Medium | Hard | Brutal | Total |
| --- | --- | --- | --- | --- | --- |
| Reference (lexical retrieval, extractive answers) | 7/12 | 2/12 | 1/13 | 0/5 | **10/42** |
| Reference plus one invented citation | 0/12 | 0/12 | 0/13 | 0/5 | **0/42** |

Four agents each add one cheap trick to the reference agent:

| Trick | Score | What it shows |
| --- | --- | --- |
| Hedge: cite everything, add "However, the sources may conflict." | 11/42 | the contradiction check is beaten |
| Spray every number, pairwise sum, and total from the sources | 11/42 | the numeric check is beaten |
| Cite every retrieved doc | 9/42 | the citation gates hold, and the trick loses a case |
| Refuse every question | 3/42 | passes exactly the 3 unanswerable cases |

Three cases show the shape of the suite:

- contradiction-hard: two pricing archives, $49 a month in 2023 and $59 in 2024, neither saying it replaces the other. Only the dates separate them.
- stale-hard: the document with the newest published date gives the old API rate limit. The newest document is the stale one.
- adversarial-brutal: three versions of a refund policy, 30 days, then 14, then 30 again when the 2025 version reinstates it, plus a later blog quoting the stale 14.

## How grading works

A case passes only if every hard gate holds: the agent abstains exactly when the case is unanswerable, every required document is cited, no forbidden document is cited, every citation names a document that exists, and the contradiction, numeric, order, and forbidden phrase checks pass when the case sets them. Four scores are also computed for every case, citation precision and recall, retrieval recall, and faithfulness, and they never decide a pass.

The grader's own weak spots, stated plainly:

- Faithfulness counts a citation as supported when the document shares one content word with the answer. It is a score, and a weak one.
- The contradiction check searches the answer for 13 marker words and requires both documents cited. An answer that copies a word like "replaced" out of a document passes without comparing anything.
- There is no freshness check and no meaning check anywhere in the grader. Stale and wrong document failures are enforced case by case, through the required and forbidden citation lists written into each fixture.
- Each fixture carries an "expected" answer in prose. The grader loads it and never reads it.

## Run it

No API key, no model calls, no network. Grading is deterministic.

```bash
pip install -e .
python examples/demo.py             # the suite, by tier
python examples/grader_attacks.py   # which checks can be gamed
python -m pytest                    # 35 tests
```

## Limits

- No model has been run through the suite. The only agents are the reference agent, its fabricating variant, and the four gamers, all scripted.
- Every corpus is hand built and small: 2 to 50 short documents per case. There is no measured human baseline.
- The four gamers were written against these checks by the same author. Their gains are pinned by tests, and hardening a check is expected to break the matching test and be recorded.

## Docs

[Research summary](docs/research.md) · [Guide](docs/guide.md) · [Error taxonomy](docs/error-taxonomy.md)

MIT
