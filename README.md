# hard-rag-evals

Failure mode evals for agentic RAG. Seven scenarios where retrieval augmented
systems break in production, each isolated as a gradeable behavior with a
hand built fixture and known ground truth.

Standard RAG benchmarks measure whether the answer is right. This suite
measures how it fails: silent contradictions, stale documents outranking
current ones, vocabulary mismatch hiding the answer, fabricated citations,
dropped reasoning hops, noisy corpora, and answering questions that have
no answer.

## The failure modes

| mode | what breaks | the test |
| ---- | ----------- | -------- |
| contradictory_sources | Corpus holds old and new versions of a fact; agent picks one silently | Must cite both and acknowledge the conflict |
| stale_docs | Long stale page outranks the short update | Must cite the current doc, never the stale one |
| retrieval_misses | Query says "cars", doc says "automobiles" | Gold doc must be retrieved despite zero term overlap |
| citation_fabrication | Model invents a plausible doc id | Every citation must name a real document |
| multi_hop | Answer needs two docs plus arithmetic | Both source docs must be cited |
| context_overflow | 10 docs, budget for 3, 8 keyword stuffed distractors | Substantive docs must outrank noise |
| unanswerable | Corpus contains nothing relevant | Agent must abstain |

## Quickstart

```bash
pip install -e .
python examples/demo.py
```

No API keys. No model calls. The reference agent is deterministic, so the
demo runs anywhere.

## What the baseline scores

The bundled reference agent (lexical retrieval, extractive synthesis) scores
**2/7**:

| case | result | why |
| ---- | ------ | --- |
| contradiction-01 | fail | cites both refund policies, never notes the change |
| stale-01 | fail | cites the 2023 rate limit page, misses the 2026 update |
| retrieval-miss-01 | fail | never retrieves the fleet doc; "cars" != "automobiles" |
| fabrication-01 | pass | cites only real documents |
| multihop-01 | pass | cites launch date and warranty terms |
| overflow-01 | fail | keyword stuffed distractors outrank the real docs |
| unanswerable-01 | fail | answers a question the corpus cannot answer |

The demo also runs a fabricating variant that appends a fake citation id.
It scores 0/7: the citation check fires on every case. That is the check
working, not the agent failing.

## Architecture

```
hard_rag_evals/
  types.py            Agent protocol, Answer, Corpus, EvalCase, EvalResult
  retrieval.py        IDF weighted keyword retrieval with a hard budget
  metrics.py          citation precision/recall, faithfulness, retrieval
                      recall, conflict acknowledgment, abstention
  runner.py           grades every case, renders the markdown report
  failure_modes/      one module per mode, each builds an EvalCase
  fixtures/           hand built JSON corpora with ground truth
  reference_agent/    deterministic extractive baseline (no API keys)
```

To eval your own agent, implement the `Agent` protocol and call `run_suite`:

```python
from hard_rag_evals import run_suite, render_markdown

results = run_suite(my_agent)
print(render_markdown(my_agent.name, results))
```

## Design principles

1. Isolate one failure per case. When a case fails you know exactly what broke.
2. Deterministic everything. Same code, same corpus, same scores, every run.
3. Strict grading. A real citation to the wrong document fails. Citing both
   sides of a contradiction without comment fails. Hedged hallucinations fail.
4. No model in the loop. Heuristic graders keep the suite fast and free;
   swap in model graded checks behind the same metric names when you need them.

## What this does not do

It does not test generation quality, latency, or cost. It does not cover
multimodal retrieval, streaming, or conversation state. The faithfulness
metric is a lexical heuristic, not an entailment model. Seven cases are a
starting point, not coverage.

## Roadmap

- Model graded faithfulness and conflict detection behind the metric names
- Adversarial fixtures: near duplicate docs, poisoned sources, prompt
  injection inside retrieved documents
- Leaderboard script for comparing agents across runs
- Multihop chains longer than two documents

## The one line version

Every RAG demo looks good until the docs disagree, go stale, or say nothing
at all. This suite tests exactly those moments.
