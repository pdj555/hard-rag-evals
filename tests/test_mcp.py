"""The MCP server, driven in-process through the SDK's own client.

The default server is for an agent under test. These tests pin what it must
not give away: no per-case grading, no failure modes, no descriptive ids.
"""
import asyncio
import json
import sys
from pathlib import Path

import jsonschema
import pytest

pytest.importorskip("mcp", reason="needs the mcp extra: pip install -e '.[mcp]'")

from mcp import Client, StdioServerParameters  # noqa: E402

from hard_rag_evals import CANARY, DATASET_VERSION, GRADER_VERSION  # noqa: E402
from hard_rag_evals import report as R  # noqa: E402
from hard_rag_evals.cli import MODES  # noqa: E402
from hard_rag_evals.failure_modes import ALL_CASES  # noqa: E402
from hard_rag_evals.mcp_server import build_server  # noqa: E402
from hard_rag_evals.runner import DEFAULT_SHUFFLE_SEED, permute_documents  # noqa: E402

GOLD = json.loads((Path(__file__).parent / "gold_answers.json").read_text())
GOLD.pop("_canary")
SCHEMA = R.load_schema()
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
RESULT = jsonschema.Draft202012Validator({**SCHEMA["$defs"]["result"], "$defs": SCHEMA["$defs"]})
PID = {c.id: R.public_id(c.id) for c in ALL_CASES}
PER_CASE_KEYS = {
    "results", "result", "case_id", "public_id", "id", "mode", "gates", "failed_gates",
    "should_abstain", "abstained", "notes", "scores", "citation_recall", "citation_precision",
    "retrieval_recall", "faithfulness", "passed_cases", "failed_cases", "cases",
}


def session(coro_fn, dev=False):
    async def go():
        async with Client(build_server(dev=dev)) as client:
            return await coro_fn(client)

    return asyncio.run(go())


def gold_answers(ids=None, key=PID):
    return [{"case_id": key[cid], **GOLD[cid]} for cid in (ids or GOLD)]


def all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from all_keys(v)


def leaks(text):
    """Mode names, descriptive ids and public ids found in a blob of output."""
    spaced = text.lower().replace("_", " ")
    return (
        [m for m in MODES if m in text or m.replace("_", " ") in spaced]
        + [c.id for c in ALL_CASES if c.id in text]
    )


# ---- what the default server offers ----


def test_default_server_has_no_per_case_grading_tool():
    tools = session(lambda c: c.list_tools()).tools
    assert sorted(t.name for t in tools) == ["get_case", "grade_submission", "list_cases"]
    assert all(t.description for t in tools)

    async def go(c):
        return await c.call_tool("grade_answer", {"case_id": PID["stale-easy"], "text": "x"})

    try:
        refused = session(go)
    except Exception:
        return  # the SDK raises for a tool that does not exist
    assert refused.is_error


def test_public_tools_carry_no_mode_and_no_descriptive_id():
    async def go(c):
        listed = await c.call_tool("list_cases", {})
        cases = [await c.call_tool("get_case", {"case_id": pid}) for pid in PID.values()]
        tools = await c.list_tools()
        return listed, cases, tools

    listed, cases, tools = session(go)
    doc = listed.structured_content
    VALIDATOR.validate(doc)
    assert doc["canary"] == CANARY
    ids = [c["id"] for c in doc["cases"]]
    assert ids == sorted(PID.values())  # public order, not the suite's order by mode
    assert all(set(c) == {"id", "difficulty", "query", "n_documents", "budget"} for c in doc["cases"])
    blob = json.dumps(doc)
    for result in cases:
        VALIDATOR.validate(result.structured_content)
        assert "mode" not in result.structured_content["case"]
        blob += json.dumps(result.structured_content) + result.content[0].text
    blob += json.dumps([t.model_dump(mode="json") for t in tools.tools])
    assert leaks(blob) == []
    for hidden in ("must_cite", "must_not_cite", "gold_doc_ids", "conflict_claims", "should_abstain"):
        assert hidden not in blob


def test_get_case_returns_the_task():
    async def go(c):
        return (
            await c.call_tool("get_case", {"case_id": PID["stale-medium"]}),
            await c.call_tool("get_case", {"case_id": "stale-medium"}),
            await c.call_tool("get_case", {"case_id": "c-000000000000"}),
            await c.call_tool("list_cases", {"difficulty": "brutal"}),
            await c.call_tool("list_cases", {"difficulty": "impossible"}),
            await c.call_tool("list_cases", {"mode": "unanswerable"}),
        )

    found, descriptive, missing, brutal, bad_tier, by_mode = session(go)
    case = next(c for c in ALL_CASES if c.id == "stale-medium")
    doc = found.structured_content["case"]
    assert doc["id"] == PID["stale-medium"] and doc["query"] == case.query
    assert {d["id"] for d in doc["documents"]} == case.corpus.ids
    # a descriptive id is not accepted: answering to it would confirm a guess at the mode
    assert descriptive.is_error and missing.is_error
    assert len(brutal.structured_content["cases"]) == 5
    assert bad_tier.is_error and "unknown difficulty" in bad_tier.content[0].text
    # there is no mode filter to probe with
    assert by_mode.is_error or len(by_mode.structured_content["cases"]) == 42


# ---- grade_submission ----


def test_grade_submission_returns_aggregates_and_no_per_case_field():
    async def go(c):
        return await c.call_tool("grade_submission", {"answers": gold_answers()})

    result = session(go)
    assert not result.is_error
    doc = result.structured_content
    VALIDATOR.validate(doc)
    assert set(doc) == {
        "kind", "schema_version", "grader_version", "dataset_version", "canary",
        "graded", "total_cases", "summary",
    }
    assert doc["kind"] == "submission"
    assert (doc["graded"], doc["total_cases"]) == (42, 42)
    assert (doc["summary"]["passed"], doc["summary"]["total"]) == (42, 42)
    assert set(doc["summary"]) == {"passed", "total", "rate", "ci95"}
    assert not {"by_tier", "easy", "medium", "hard", "brutal"} & set(all_keys(doc))
    assert doc["grader_version"] == GRADER_VERSION and doc["dataset_version"] == DATASET_VERSION
    assert not set(all_keys(doc)) & PER_CASE_KEYS
    blob = json.dumps(doc) + result.content[0].text
    assert leaks(blob) == [] and not any(pid in blob for pid in PID.values())


def test_grade_submission_counts_failures_without_saying_which():
    answers = gold_answers()
    for a in answers[:7]:
        a["citations"] = ["doc-not-in-corpus"]

    async def go(c):
        return await c.call_tool("grade_submission", {"answers": answers})

    doc = session(go).structured_content
    assert (doc["summary"]["passed"], doc["summary"]["total"]) == (35, 42)
    assert not set(all_keys(doc)) & PER_CASE_KEYS
    assert "doc-not-in-corpus" not in json.dumps(doc)


def test_a_server_grades_one_submission_so_two_cannot_be_differenced():
    flipped = gold_answers()
    flipped[0]["abstained"] = not flipped[0]["abstained"]

    async def go(c):
        first = await c.call_tool("grade_submission", {"answers": gold_answers()})
        second = await c.call_tool("grade_submission", {"answers": flipped})
        return first, second

    first, second = session(go)
    assert not first.is_error
    assert second.is_error and "already graded a submission" in second.content[0].text
    assert second.structured_content is None


def test_concurrent_submissions_grade_exactly_one():
    # The SDK runs tools on worker threads. Five submissions sent at once,
    # each abstaining on a different number of cases so their scores differ:
    # exactly one may come back graded, or the others give verdicts away.
    def submission(n):
        answers = gold_answers()
        for a in answers[:n]:
            a["abstained"] = not a["abstained"]
        answers[0]["text"] = "x " * 200000  # slow to parse, to widen the window
        return answers

    async def go(c):
        calls = [c.call_tool("grade_submission", {"answers": submission(n)}) for n in range(5)]
        return await asyncio.gather(*calls, return_exceptions=True)

    for _ in range(3):
        results = session(go)
        graded = [r for r in results if not isinstance(r, Exception) and not r.is_error]
        assert len(graded) == 1, [getattr(r, "is_error", r) for r in results]
        refused = [r for r in results if not isinstance(r, Exception) and r.is_error]
        assert len(refused) == 4
        assert all("already graded a submission" in r.content[0].text for r in refused)


def test_a_refused_submission_does_not_use_up_the_one_allowed():
    async def go(c):
        bad = await c.call_tool("grade_submission", {"answers": gold_answers()[:5]})
        good = await c.call_tool("grade_submission", {"answers": gold_answers()})
        return bad, good

    bad, good = session(go)
    assert bad.is_error and not good.is_error


def test_only_a_submission_for_all_42_cases_is_graded():
    ids = list(GOLD)

    async def go(c):
        tools = await c.list_tools()
        schema = next(t.input_schema for t in tools.tools if t.name == "grade_submission")
        attempts = [
            await c.call_tool("grade_submission", {"answers": gold_answers(ids[:n])})
            for n in (1, 10, 12, 41)
        ]
        declared = await c.call_tool(
            "grade_submission",
            {"answers": gold_answers(ids[:12]), "case_ids": [PID[i] for i in ids[:12]]},
        )
        return schema, attempts, declared

    schema, attempts, declared = session(go)
    assert set(schema["properties"]) == {"answers"}  # no way to declare a subset
    for refused in attempts:
        assert refused.is_error and refused.structured_content is None
        assert "must answer all 42 cases" in refused.content[0].text
    assert declared.is_error and declared.structured_content is None


def test_get_case_presents_documents_shuffled_with_the_published_seed():
    async def go(c):
        return [await c.call_tool("get_case", {"case_id": PID[case.id]}) for case in ALL_CASES]

    first_is_required = 0
    for case, result in zip(ALL_CASES, session(go)):
        doc = result.structured_content
        assert doc["shuffle_seed"] == DEFAULT_SHUFFLE_SEED
        ids = [d["id"] for d in doc["case"]["documents"]]
        assert ids == [d.id for d in permute_documents(case, DEFAULT_SHUFFLE_SEED).corpus.documents]
        first_is_required += ids[0] in case.must_cite
    assert first_is_required == 22  # 33 in fixture order


@pytest.mark.parametrize(
    "mutate,complaint",
    [
        (lambda a: a[0].update(case_id="stale-easy"), "unknown case"),
        (lambda a: a[0].update(case_id="c-000000000000"), "unknown case"),
        (lambda a: a.append(dict(a[0])), "answered more than once"),
        (lambda a: a[0].update(citation=["x"]), "unknown keys"),
        (lambda a: a[0].pop("text"), "'text' is required"),
        (lambda a: a.pop(), "1 have no answer"),
        (lambda a: a[0].update(text="\ud800"), "not valid Unicode"),
    ],
)
def test_grade_submission_rejects_malformed_submissions(mutate, complaint):
    answers = gold_answers()
    mutate(answers)

    async def go(c):
        return await c.call_tool("grade_submission", {"answers": answers})

    refused = session(go)
    assert refused.is_error and complaint in refused.content[0].text


# ---- --dev ----


def test_dev_server_adds_per_case_grading_and_says_what_it_costs():
    async def go(c):
        tools = await c.list_tools()
        bad = {"case_id": "stale-medium", "text": "The limit is 100.", "citations": ["doc-ratelimit-2023"]}
        return (
            tools,
            await c.call_tool("grade_answer", bad),
            await c.call_tool("grade_answer", {"case_id": PID["stale-easy"], **GOLD["stale-easy"]}),
            await c.call_tool("list_cases", {}),
            await c.call_tool("grade_submission", {"answers": gold_answers(key={k: k for k in GOLD})}),
            await c.call_tool("grade_submission", {"answers": gold_answers()}),
        )

    tools, bad, good, listed, first, second = session(go, dev=True)
    assert sorted(t.name for t in tools.tools) == ["get_case", "grade_answer", "grade_submission", "list_cases"]
    description = next(t.description for t in tools.tools if t.name == "grade_answer")
    assert "DEV ONLY" in description and "means nothing" in description
    RESULT.validate(bad.structured_content)
    assert "forbidden_citation" in bad.structured_content["failed_gates"]
    assert any("doc-ratelimit-2023" in n for n in bad.structured_content["notes"])
    assert good.structured_content["passed"]
    VALIDATOR.validate(listed.structured_content)
    assert [c["case_id"] for c in listed.structured_content["cases"]] == [c.id for c in ALL_CASES]
    assert listed.structured_content["cases"][0]["mode"] == ALL_CASES[0].mode
    assert not first.is_error and not second.is_error  # no one-submission limit in dev


def test_dev_grade_answer_agrees_with_the_grader_on_every_gold_answer():
    async def go(c):
        return {
            cid: await c.call_tool("grade_answer", {"case_id": cid, **GOLD[cid]}) for cid in GOLD
        }

    for case_id, result in session(go, dev=True).items():
        assert not result.is_error, case_id
        assert result.structured_content["passed"], case_id


# ---- over real stdio ----


def stdio(*flags):
    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "hard_rag_evals", "mcp", *flags])
        async with Client(params) as client:
            tools = await client.list_tools()
            listed = await client.call_tool("list_cases", {"difficulty": "easy"})
            return sorted(t.name for t in tools.tools), listed.structured_content

    return asyncio.run(go())


def test_mcp_subcommand_serves_the_public_server_over_stdio():
    names, doc = stdio()
    assert names == ["get_case", "grade_submission", "list_cases"]
    assert len(doc["cases"]) == 12 and "mode" not in doc["cases"][0]


def test_mcp_subcommand_dev_flag_is_what_adds_grade_answer():
    names, doc = stdio("--dev")
    assert "grade_answer" in names and "mode" in doc["cases"][0]
