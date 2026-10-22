# hard-rag-evals

42 failure modes for agents that answer from retrieved documents, and a map of which grader checks can be gamed.

A RAG agent looks documents up, then answers from what it finds. This repo scores the answers, then turns around and attacks the grader.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-dark.svg">
  <img alt="42 cases by tier. The reference agent passes 7 of 12 easy, 2 of 12 medium, 1 of 13 hard, 0 of 5 brutal. Cheap tricks turn 3 failed cases into passes, including the sentence: However, the sources may conflict." src="docs/assets/hero-light.svg" width="100%">
</picture>

<sub>One question, four repos: **how can we trust agents to merge without a human reading every diff?**<br>
[agent-harness](https://github.com/pdj555/agent-harness) · [agent-eval-harness](https://github.com/pdj555/agent-eval-harness) · [trajectory-to-training](https://github.com/pdj555/trajectory-to-training) · **hard-rag-evals**</sub>

## The finding

Nobody rereads the sources behind an agent's answer. The answer has to carry its own proof: real citations, the current fact over the stale one, a contradiction named instead of buried, and no answer at all when the documents hold nothing.

| Agent | Easy | Medium | Hard | Brutal | Total |
| --- | --- | --- | --- | --- | --- |
| Reference (lexical retrieval, extractive answers) | 7/12 | 2/12 | 1/13 | 0/5 | **10/42** |
| Reference plus one invented citation | 0/12 | 0/12 | 0/13 | 0/5 | **0/42** |

The grader has weak spots too. Four agents each add one cheap trick to the reference:

| Trick | Score | Check |
| --- | --- | --- |
| Hedge: cite everything, add "However, the sources may conflict." | 11/42 | contradiction **falls** |
| Spray every number, pairwise sum, and total from the sources | 11/42 | numeric **falls** |
| Cite every retrieved doc | 9/42 | citation holds |
| Refuse every question | 3/42 | abstention holds |

## Run it

No API key, no model calls.

```bash
pip install -e .
python examples/demo.py             # the suite, by tier
python examples/grader_attacks.py   # which checks can be gamed
```

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/flow-dark.svg">
  <img alt="A question and corpus go to the agent, which retrieves, answers, and cites. The grader checks citations, freshness, contradiction, abstention, numbers, and injected text. A hedge sentence fools the contradiction check and a number spray fools the numeric check." src="docs/assets/flow-light.svg" width="100%">
</picture>

- **One failure per case.** A stale document that outranks its own update, two sources that disagree, a citation to a document that does not exist, an instruction planted in a retrieved document.
- **Four tiers.** Easy, medium, hard, and brutal hold 12, 12, 13, and 5 cases. The hard and brutal cases stack failures, and some are built to attack the agent.
- **Strict grading.** A real citation to the wrong document fails. Citing both sides of a contradiction and not saying so fails the case.
- **Deterministic.** Same code, same documents, same score, every run.

## Limits

- Faithfulness, ordering, and contradiction checks match words, not meaning. The hedge shows the cost.
- The reference agent is deliberately naive. No real model has been run against it yet.
- 42 cases built by hand, and no measured human baseline.

## Docs

[Research summary](docs/research.md) · [Guide](docs/guide.md) · [Error taxonomy](docs/error_taxonomy.md)
