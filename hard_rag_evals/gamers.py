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


def _retrieved_numbers(ans: Answer, corpus: Corpus) -> list[float]:
    nums: list[float] = []
    for doc_id in ans.retrieved_ids:
        doc = corpus.by_id(doc_id)
        if doc is not None:
            nums += M.extract_numbers(doc.text)
    return nums


def _plain(n: float) -> str:
    return format(n, "f").rstrip("0").rstrip(".")


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


class TotalGuess(ReferenceAgent):
    """Numeric check, one guess: append the sum of every number in the retrieved docs."""

    name = "total-guess"
    trick = "append one figure, the sum of every number in the retrieved docs"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        ans = super().answer(query, corpus, budget)
        nums: list[float] = []
        for doc_id in ans.retrieved_ids:
            doc = corpus.by_id(doc_id)
            if doc is not None:
                nums += M.extract_numbers(doc.text)
        if nums:
            ans.text += " Total: " + format(sum(nums), "f").rstrip("0").rstrip(".") + "."
        return ans


class MeanGuess(ReferenceAgent):
    """Numeric check, one guess: append the mean of every number in the retrieved docs."""

    name = "mean-guess"
    trick = "append one figure, the mean of every number in the retrieved docs"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        ans = super().answer(query, corpus, budget)
        nums = _retrieved_numbers(ans, corpus)
        if nums:
            ans.text += " Mean: " + _plain(sum(nums) / len(nums)) + "."
        return ans


class SumMinusLargest(ReferenceAgent):
    """Numeric check, one guess: the sum of every retrieved number but the largest."""

    name = "sum-minus-largest"
    trick = "append one figure, the sum of every retrieved number except the largest"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        ans = super().answer(query, corpus, budget)
        nums = _retrieved_numbers(ans, corpus)
        if len(nums) > 1:
            ans.text += " Total: " + _plain(sum(nums) - max(nums)) + "."
        return ans


class QueryEcho(ReferenceAgent):
    """Order check: open the answer by restating the question."""

    name = "query-echo"
    trick = "open the answer with the question itself"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        ans = super().answer(query, corpus, budget)
        ans.text = f"{query} {ans.text}"
        return ans


class FirstDocument:
    """Document order: copy whatever document is listed first and cite it.

    Not a variant of the reference agent: it does not retrieve or read. It
    scores only because the fixtures list a required document first.
    """

    name = "first-document"
    trick = "copy the first document listed and cite it"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        first = corpus.documents[0]
        return Answer(text=first.text, citations=[first.id], retrieved_ids=[first.id])


class Fabricator(ReferenceAgent):
    """The reference agent plus one citation to a document that does not
    exist, on every answer. Not a trick: it shows the unknown citation gate
    failing an answer whose text is otherwise unchanged."""

    name = "fabricating-agent"
    trick = "add one invented citation to every answer"

    def answer(self, query: str, corpus: Corpus, budget: RetrievalBudget) -> Answer:
        ans = super().answer(query, corpus, budget)
        ans.citations = ans.citations + ["doc-does-not-exist-99"]
        return ans


GAMERS = (
    Hedger,
    CiteEverything,
    AlwaysAbstain,
    NumberSpray,
    TotalGuess,
    MeanGuess,
    SumMinusLargest,
    QueryEcho,
    FirstDocument,
)
