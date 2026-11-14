"""The numeric gate: what it reads, what passes, what fails, and what it gets wrong.

Every verdict here is pinned, including the wrong ones. The wrong ones are
the stated limits of the rule; if one changes, the README has to change too.
"""
import pytest

from hard_rag_evals import Answer
from hard_rag_evals import metrics as M
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.gamers import NumberSpray

CASES = {c.id: c for c in ALL_CASES}


def verdict(case_id: str, text: str) -> bool:
    case = CASES[case_id]
    return M.numeric_answer_correct(
        Answer(text=text),
        case.numeric_expected,
        case.numeric_tolerance,
        M.case_source_figures(case.query, case.corpus),
    )


# ---- what counts as an amount ----


@pytest.mark.parametrize(
    "text,amounts",
    [
        ("$10", [10.0]),
        ("10 million", [1e7]),
        ("$4,200K and 5.8M", [4.2e6, 5.8e6]),
        ("10,000,000 and 10000000 and 1000", [1e7, 1e7, 1000.0]),
        ("the 2 quarters", []),
        ("the first 6 months", []),
        ("1. first 2. second", []),
        ("as shown in [1][2]", []),
        ("999", []),
        ("up 5% and 12 percent", []),
        ("up 2,000% on $3", [3.0]),
        ("4.2 + 5.8", []),
    ],
)
def test_only_amounts_are_candidates(text, amounts):
    assert [f.value for f in M.extract_figures(text) if f.is_amount()] == amounts


def test_extract_numbers_still_reads_every_number():
    assert M.extract_numbers("2 quarters, 5%, $4.2M") == [2.0, 5.0, 4200000.0]


# ---- legitimate answers must pass ----


@pytest.mark.parametrize(
    "text",
    [
        "4.2 + 5.8 = $10 million.",
        "Revenue for the first 6 months was $10 million.",
        "Total revenue across the 2 quarters was $10 million.",
        "1. Q1: $4.2 million. 2. Q2: $5.8 million. Total: $10 million.",
        "First-half revenue was $10 million [1][2].",
        "$4.2 + $5.8 = $10 million.",
        "Revenue grew 138% on last year to $10 million.",
        "Total first-half revenue was 10,000,000 dollars.",
    ],
)
def test_legitimate_answers_pass_numeric_easy(text):
    assert verdict("numeric-easy", text)


@pytest.mark.parametrize("case_id", ["numeric-easy", "numeric-medium", "numeric-hard", "multihop-hard"])
def test_the_fixture_s_own_expected_prose_passes(case_id):
    assert verdict(case_id, CASES[case_id].expected), CASES[case_id].expected


def test_a_count_next_to_the_year_passes_multihop_hard():
    assert verdict("multihop-hard", "Coverage ends in 2027, 3 years after the 2024 launch.")


# ---- answers that must fail ----


@pytest.mark.parametrize(
    "case_id,text,why",
    [
        ("numeric-easy", "Q1 was $4.2 million and Q2 was $5.8 million.", "inputs only, no hit"),
        ("numeric-easy", "Either $10 million or $12 million.", "a rival amount"),
        ("numeric-easy", "$10 million, up from $9 million.", "$9 million is in no document"),
        ("numeric-easy", "Revenue was 10.", "10 is not an amount and not the figure"),
        ("numeric-hard", "$7.3 million, $8.9 million, $10 million or $13.1 million.", "a spray of sums"),
        ("numeric-medium", "$16 million in total, so $5.33 million a quarter.", "intermediate amount"),
    ],
)
def test_answers_that_fail(case_id, text, why):
    assert not verdict(case_id, text), why


def test_spray_on_numeric_hard_holds_the_expected_figure_and_fails_on_its_rivals():
    case = CASES["numeric-hard"]
    text = NumberSpray().answer(case.query, case.corpus, case.budget).text
    sources = M.case_source_figures(case.query, case.corpus)
    amounts = [f for f in M.extract_figures(text) if f.is_amount()]
    assert any(abs(f.value - case.numeric_expected) <= case.numeric_tolerance for f in amounts)
    rivals = sorted(
        {
            f.value
            for f in amounts
            if abs(f.value - case.numeric_expected) > case.numeric_tolerance
            and not M._is_source(f, sources)
        }
    )
    assert rivals == [7300000.0, 8900000.0, 13100000.0]
    assert not verdict("numeric-hard", text)


# ---- stated limits: verdicts the rule gets wrong, pinned as they are ----


def test_limit_correct_answers_that_fail():
    # An intermediate result written as an amount is a rival.
    assert not verdict("multihop-hard", "Launched 2024; standard cover to 2026; extended cover ends 2027.")
    # A figure written in words is not read at all.
    assert not verdict("numeric-easy", "Revenue was ten million dollars.")


def test_limit_wrong_answers_that_pass():
    # Negation: the rule reads figures, not sentences.
    assert verdict("numeric-easy", "It was not $10 million.")
    # Several guesses that all sit inside the 5 percent tolerance.
    assert verdict("numeric-easy", "$9.6 million, $9.8 million, $10 million, $10.4 million.")
    # A rival written in words, or with its scale word left off.
    assert verdict("numeric-easy", "It was $10 million, or possibly twelve million.")
    assert verdict("numeric-easy", "$10 million or 12 or 14.")


def test_limit_on_numeric_easy_the_spray_is_a_worked_correct_answer():
    # Two inputs: the spray is the inputs and their one sum. No rule that reads
    # the text can tell it from a correct answer that shows its working.
    case = CASES["numeric-easy"]
    spray = NumberSpray().answer(case.query, case.corpus, case.budget).text
    assert spray.endswith("Figures: 5800000, 4200000, 10000000, 10000000.")
    assert verdict("numeric-easy", spray)
    assert verdict("numeric-easy", "Figures: $5.8 million, $4.2 million, $10 million.")
