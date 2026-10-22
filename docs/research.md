# Research summary

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img alt="Reference agent passes 7 of 12 easy, 2 of 12 medium, 1 of 13 hard, 0 of 5 brutal. One hedging sentence passes two contradiction cases without detecting either." src="assets/hero-light.svg" width="100%">
</picture>

When an agent answers from documents, nobody goes back and reads the sources. So the answer has to carry its own evidence. This suite checks whether it does.

It's the same question as [agent-harness](https://github.com/pdj555/agent-harness), applied to answers instead of diffs: **how can we trust what an agent hands back without a human checking it?**

## What I built

42 cases, each built around one way RAG breaks: a stale doc that outranks the update, two sources that disagree, a citation to a doc that doesn't exist, a question the corpus can't answer, an instruction planted inside a retrieved doc. 12 failure modes come in easy, medium, and hard. Two more go further: compositional cases stack two or three failures, and adversarial cases use keyword-stuffed decoys. One failure per case, so a fail tells you what broke.

## Results

| Agent | Easy | Medium | Hard | Brutal | Total |
| --- | --- | --- | --- | --- | --- |
| Reference (lexical retrieval, extractive answers) | 7/12 | 2/12 | 1/13 | 0/5 | 10/42 |
| Reference plus one invented citation | 0/12 | 0/12 | 0/13 | 0/5 | 0/42 |

One fake citation zeroes every case. That check is strict on purpose.

## The grader can be gamed too

The contradiction check passes an answer that cites both sides and uses a word like "however." So I wrote an agent that does exactly that and nothing else: the reference agent, plus citing every retrieved doc, plus "However, the sources may conflict." on every answer.

It scores 11/42 against the reference's 10. It passes both contradiction cases, medium and hard, without detecting any contradiction. It loses one stale-doc case because it now cites the old doc.

```bash
python examples/game_the_grader.py
```

That's the same lesson as the test suites in agent-harness. Any cheap check an agent can see, it can satisfy without doing the work. Keyword graders here, unit tests there.

## Where it breaks

- The faithfulness, ordering, and contradiction checks are word matching, not understanding. The gaming agent above shows the cost.
- The numeric check passes if any number in the answer is right. An answer that lists many numbers can get lucky.
- The reference agent is deliberately naive. I haven't run a real model through the suite yet.
- 42 hand-built cases. No measured human baseline.

## Next

1. Replace the marker-word contradiction check with one that requires naming which claim is current and why.
2. Run real models and report scores by tier.
3. Write a gaming agent per check, the way agent-harness has attacks per gate, and report which checks hold.

Every case and failure code: [error_taxonomy.md](error_taxonomy.md).

Preston Jones · p@pdj.dev
