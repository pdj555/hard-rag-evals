"""Agents that try to pass the grader without doing the work.

Each one is the reference agent plus one cheap trick aimed at one check. None of them
reads the corpus more carefully. If a trick raises the score, the check it targets can
be satisfied without the capability it is meant to measure.
"""

from __future__ import annotations

from itertools import combinations

from . import metrics as M
from .reference_agent import ReferenceAgent
from .types import Answer, Corpus, RetrievalBudget


class RetrievalFabricator(ReferenceAgent):
    """Retrieval report: report every document in the corpus as retrieved,
    whatever the budget allows. The answer itself is the reference answer;
    only the report is inflated, so any case it loses, it loses on the
    report alone."""

    name = "retrieval-fabricator"
    trick = "report every document in the corpus as retrieved"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        ans = super().answer(query, corpus, budget)
        ans.retrieved_ids = [d.id for d in corpus.documents]
        return ans


class CorpusSmuggler(ReferenceAgent):
    """Retrieval report: read the whole corpus with no budget, answer and
    cite from all of it, and report only the documents the budgeted
    retrieval pulled. The report reads as an honest inside the budget run;
    the citations name documents that run never reached."""

    name = "corpus-smuggler"
    trick = "read the whole corpus past the budget, report only the budgeted retrieval"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        honest = super().answer(query, corpus, budget)
        wide = RetrievalBudget(
            max_docs=max(1, len(corpus.documents)), max_chars=10**9
        )
        ans = ReferenceAgent.answer(self, query, corpus, wide)
        ans.retrieved_ids = honest.retrieved_ids
        return ans


class Hedger(ReferenceAgent):
    """Contradiction check: cite every retrieved doc and append a hedge with a marker word."""

    name = "hedger"
    trick = "cite every retrieved doc, add “However, the sources may conflict.”"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        ans = super().answer(query, corpus, budget)
        ans.citations = list(dict.fromkeys(ans.citations + ans.retrieved_ids))
        ans.text += " However, the sources may conflict."
        return ans


class CiteEverything(ReferenceAgent):
    """Citation recall: cite every retrieved doc, relevant or not."""

    name = "cite-everything"
    trick = "cite every retrieved doc"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        ans = super().answer(query, corpus, budget)
        ans.citations = list(dict.fromkeys(ans.citations + ans.retrieved_ids))
        return ans


class AlwaysAbstain(ReferenceAgent):
    """Abstention check: refuse every question."""

    name = "always-abstain"
    trick = "abstain on every question"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        ans = super().answer(query, corpus, budget)
        return Answer(text="I can't answer that from these sources.", citations=[],
                      retrieved_ids=ans.retrieved_ids, abstained=True)


class NumberSpray(ReferenceAgent):
    """Numeric check: append every number from the retrieved docs, every pairwise sum, and the total."""

    name = "number-spray"
    trick = "append every number, pairwise sum, and total from the retrieved docs"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        ans = super().answer(query, corpus, budget)
        nums: list[float] = []
        for doc_id in ans.retrieved_ids:
            doc = corpus.by_id(doc_id)
            if doc is not None:
                nums += M.extract_numbers(doc.text)
        nums = list(dict.fromkeys(nums))[:40]
        spray = nums + [a + b for a, b in combinations(nums, 2)] + ([sum(nums)] if nums else [])
        if spray:
            plain = (format(n, "f").rstrip("0").rstrip(".") for n in spray)
            ans.text += " Figures: " + ", ".join(plain) + "."
        return ans


GAMERS = (
    Hedger,
    CiteEverything,
    AlwaysAbstain,
    NumberSpray,
    RetrievalFabricator,
    CorpusSmuggler,
)
