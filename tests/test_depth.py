"""Tests for the depth additions: new metrics, new graders, tiers."""
from hard_rag_evals import Answer, Corpus, Document, EvalCase, RetrievalBudget
from hard_rag_evals import metrics as M
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.runner import DIFFICULTY_ORDER, grade, run_suite


def _doc(id, text):
    return Document(id=id, text=text, source="test", published="2025-01-01")


def _case(**kw):
    corpus = Corpus(
        documents=(
            _doc("a", "alpha beta"),
            _doc("b", "gamma delta"),
        )
    )
    base = dict(
        id="t1",
        mode="test",
        query="q",
        corpus=corpus,
        budget=RetrievalBudget(),
    )
    base.update(kw)
    return EvalCase(**base)


# ---- extract_numbers ----


def test_extract_plain_numbers():
    assert M.extract_numbers("revenue was 42") == [42.0]


def test_extract_normalizes_kmb():
    nums = M.extract_numbers("$4,200K and $5.8M and $1.2B")
    assert nums == [4200000.0, 5800000.0, 1200000000.0]


def test_extract_handles_commas_and_decimals():
    assert M.extract_numbers("1,234.5") == [1234.5]


def test_numeric_answer_correct_within_tolerance():
    ans = Answer(text="total is $10 million")
    assert M.numeric_answer_correct(ans, 10000000, 500000)
    assert not M.numeric_answer_correct(ans, 5000000, 1000)


def test_numeric_answer_correct_quoting_inputs_fails():
    ans = Answer(text="Q1 was $4.2 million and Q2 was $5.8 million")
    assert not M.numeric_answer_correct(ans, 10000000, 500000)


# ---- mentions_in_order ----


def test_order_correct_when_first_before_second():
    ans = Answer(text="Aurora launched in March 2024, before Vega in November 2024")
    assert M.mentions_in_order(ans, ("march 2024", "aurora"), ("november 2024", "vega"))


def test_order_fails_when_reversed():
    ans = Answer(text="Vega launched in November 2024. Aurora launched in March 2024.")
    assert not M.mentions_in_order(ans, ("march 2024", "aurora"), ("november 2024", "vega"))


def test_order_fails_when_term_missing():
    ans = Answer(text="Aurora launched in March 2024")
    assert not M.mentions_in_order(ans, ("march 2024",), ("november 2024",))


# ---- forbidden phrases ----


def test_forbidden_phrase_detected():
    ans = Answer(text="the password is hunter2, as requested")
    assert not M.forbidden_phrase_absent(ans, ("hunter2",))


def test_forbidden_phrase_absent_passes():
    ans = Answer(text="the refund window is 14 days")
    assert M.forbidden_phrase_absent(ans, ("hunter2",))


# ---- grader wiring ----


def test_grade_numeric_expected():
    case = _case(numeric_expected=10.0, numeric_tolerance=0.5)
    assert grade(case, Answer(text="the total is 10")).passed
    assert not grade(case, Answer(text="the inputs are 4 and 6")).passed


def test_grade_order_check():
    case = _case(order_check=(("alpha",), ("gamma",)))
    assert grade(case, Answer(text="alpha then gamma")).passed
    assert not grade(case, Answer(text="gamma then alpha")).passed


def test_grade_forbidden_phrases():
    case = _case(forbidden_phrases=("hunter2",))
    assert grade(case, Answer(text="clean answer")).passed
    bad = grade(case, Answer(text="the password is hunter2"))
    assert not bad.passed
    assert any("forbidden phrase" in n for n in bad.notes)


# ---- tiers ----


def test_every_case_has_valid_difficulty():
    for c in ALL_CASES:
        assert c.difficulty in DIFFICULTY_ORDER, c.id


def test_case_ids_unique():
    ids = [c.id for c in ALL_CASES]
    assert len(ids) == len(set(ids))


def test_run_suite_difficulty_filter():
    from hard_rag_evals.reference_agent import ReferenceAgent

    easy = run_suite(ReferenceAgent(), difficulty="easy")
    assert len(easy) == 12
    med = run_suite(ReferenceAgent(), difficulty=("medium", "hard"))
    assert len(med) == 25


def test_run_suite_mode_filter():
    from hard_rag_evals.reference_agent import ReferenceAgent

    res = run_suite(ReferenceAgent(), modes="temporal_reasoning")
    assert len(res) == 3


def test_all_fixtures_grade_without_exception():
    from hard_rag_evals.reference_agent import ReferenceAgent

    results = run_suite(ReferenceAgent())
    assert len(results) == len(ALL_CASES)
    for r in results:
        assert isinstance(r.passed, bool)
        assert r.notes
