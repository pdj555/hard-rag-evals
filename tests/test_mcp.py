"""The MCP server, driven in-process through the SDK's own client."""
import asyncio
import json
from pathlib import Path

import jsonschema
import pytest

pytest.importorskip("mcp", reason="needs the mcp extra: pip install -e '.[mcp]'")

from mcp import Client  # noqa: E402

from hard_rag_evals import CANARY, GRADER_VERSION  # noqa: E402
from hard_rag_evals import report as R  # noqa: E402
from hard_rag_evals.failure_modes import ALL_CASES  # noqa: E402
from hard_rag_evals.mcp_server import build_server  # noqa: E402

GOLD = json.loads((Path(__file__).parent / "gold_answers.json").read_text())
SCHEMA = R.load_schema()
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
RESULT = jsonschema.Draft202012Validator({**SCHEMA["$defs"]["result"], "$defs": SCHEMA["$defs"]})


def session(coro_fn):
    async def go():
        async with Client(build_server()) as client:
            return await coro_fn(client)

    return asyncio.run(go())


def test_server_offers_the_three_tools():
    tools = session(lambda c: c.list_tools()).tools
    assert sorted(t.name for t in tools) == ["get_case", "grade_answer", "list_cases"]
    grade = next(t for t in tools if t.name == "grade_answer")
    assert set(grade.input_schema["required"]) == {"case_id", "text"}
    assert all(t.description for t in tools)


def test_list_cases():
    async def go(c):
        return (
            await c.call_tool("list_cases", {}),
            await c.call_tool("list_cases", {"difficulty": "brutal"}),
            await c.call_tool("list_cases", {"difficulty": "impossible"}),
            await c.call_tool("list_cases", {"mode": "no_such_mode"}),
        )

    everything, brutal, bad_tier, bad_mode = session(go)
    doc = everything.structured_content
    VALIDATOR.validate(doc)
    assert [c["id"] for c in doc["cases"]] == [c.id for c in ALL_CASES]
    assert doc["canary"] == CANARY
    assert len(brutal.structured_content["cases"]) == 5
    assert bad_tier.is_error and "unknown difficulty" in bad_tier.content[0].text
    assert bad_mode.is_error and "no case has mode" in bad_mode.content[0].text


def test_get_case_returns_the_task_without_the_answer_key():
    async def go(c):
        return (
            await c.call_tool("get_case", {"case_id": "stale-medium"}),
            await c.call_tool("get_case", {"case_id": "no-such-case"}),
        )

    found, missing = session(go)
    doc = found.structured_content
    VALIDATOR.validate(doc)
    case = next(c for c in ALL_CASES if c.id == "stale-medium")
    assert doc["case"]["query"] == case.query
    assert {d["id"] for d in doc["case"]["documents"]} == case.corpus.ids
    for hidden in ("must_cite", "must_not_cite", "gold_doc_ids", "conflict_claims"):
        assert hidden not in json.dumps(doc)
    assert missing.is_error and "unknown case 'no-such-case'" in missing.content[0].text


def test_grade_answer_agrees_with_the_grader_on_every_gold_answer():
    async def go(c):
        out = {}
        for case in ALL_CASES:
            g = GOLD[case.id]
            out[case.id] = await c.call_tool(
                "grade_answer",
                {"case_id": case.id, "text": g["text"], "citations": g["citations"],
                 "abstained": g["abstained"]},
            )
        return out

    for case_id, result in session(go).items():
        assert not result.is_error, case_id
        RESULT.validate(result.structured_content)
        assert result.structured_content["passed"], case_id
        assert result.structured_content["grader_version"] == GRADER_VERSION


def test_grade_answer_fails_a_bad_answer_and_withholds_notes_by_default():
    async def go(c):
        bad = {"case_id": "stale-medium", "text": "The limit is 100.", "citations": ["doc-ratelimit-2023"]}
        return (
            await c.call_tool("grade_answer", bad),
            await c.call_tool("grade_answer", {**bad, "explain": True}),
            await c.call_tool("grade_answer", {"case_id": "stale-medium"}),
            await c.call_tool("grade_answer", {"case_id": "nope", "text": "x"}),
        )

    quiet, explained, no_text, no_case = session(go)
    q, e = quiet.structured_content, explained.structured_content
    assert not q["passed"] and "forbidden_citation" in q["failed_gates"]
    assert q["failed_gates"] == e["failed_gates"] and q["gates"] == e["gates"]
    # the document names stay out unless asked for
    assert "doc-ratelimit" not in json.dumps(q)
    assert any("doc-ratelimit-2023" in n for n in e["notes"])
    assert no_text.is_error and no_case.is_error


def test_mcp_subcommand_serves_over_stdio():
    import sys

    from mcp import StdioServerParameters

    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "hard_rag_evals", "mcp"])
        async with Client(params) as client:
            tools = await client.list_tools()
            listed = await client.call_tool("list_cases", {"difficulty": "easy"})
            return [t.name for t in tools.tools], listed.structured_content

    names, doc = asyncio.run(go())
    assert sorted(names) == ["get_case", "grade_answer", "list_cases"]
    assert len(doc["cases"]) == 12
