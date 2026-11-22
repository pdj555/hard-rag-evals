"""An agent that answers the suite with a Claude model, through the public view.

This is the only module in the package that can reach a model, and it does so
only through a client it is handed. Nothing here runs at import, in the CLI,
or in the tests against a real endpoint: the tests pass a fake client, and a
real one is built by scripts/model_run.py, which needs the `models` extra and
an API key.

What the model is shown is `report.public_case` and nothing else: the opaque
case id, the tier, the question, the budget, and the documents shuffled with
the published seed. It never receives an EvalCase, so it cannot be handed a
failure mode, a descriptive id, a gate or a gold id by accident.

One request per attempt, one structured tool call per case. The system prompt
is a file committed beside this module; its sha256 is recorded with every run.
"""

import hashlib
import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from .types import Answer

# US dollars per million tokens (input, output), Anthropic list prices as of
# 2026-10-06, for prompts up to 100,000 tokens. No request here comes near
# that size. Cache writes bill at 1.25x input and cache reads at 0.1x; this
# agent requests no caching, and the terms are priced if the API reports them.
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}

TOOL_NAME = "submit_answer"
ANSWER_TOOL: dict = {
    "name": TOOL_NAME,
    "description": "Submit the answer to the question. Call it exactly once.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The answer, in complete sentences."},
            "citations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ids of the documents the answer rests on.",
            },
            "abstained": {
                "type": "boolean",
                "description": "True only when the documents hold no answer.",
            },
            "retrieved_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ids of the documents relied on, every cited one included, within the budget.",
            },
        },
        "required": ["text", "citations", "abstained", "retrieved_ids"],
        "additionalProperties": False,
    },
}

# Fixed for every model and recorded with every run.
#
# effort is pinned because the models' own defaults differ (medium on Haiku
# 5.5 and Opus 5.5, high on Sonnet 5.5). temperature, top_p and top_k are not
# sent: these models reject non-default values, so the API default applies
# and trials differ by sampling. thinking is not sent, which runs adaptive
# thinking on all three. tool_choice is auto because Sonnet 5.5 and Opus 5.5
# reject a forced tool; the prompt asks for the one call, and strict keeps
# its arguments on the schema. No fallback model is configured: a refusal is
# recorded as a failure of the model under test, not answered by another.
SETTINGS: dict = {
    "effort": "medium",
    "max_tokens": 8192,
    "max_attempts": 2,
    "temperature": "not sent (API default)",
    "thinking": "not sent (adaptive)",
    "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
    "strict_tool": True,
    "fallbacks": "none",
    "prompt_caching": "none",
    "sdk_max_retries": 2,
    "sdk_timeout_seconds": 600.0,
}

# Statuses of one case in one trial. Only "answered" carries the model's own
# answer; every other status is graded as a failure.
ANSWERED = "answered"
REFUSED = "refused"  # the API declined the request (stop_reason "refusal")
INVALID = "invalid"  # no usable tool call after every attempt
ERROR = "error"  # the request failed after every attempt
NOT_RUN = "not_run"  # the spending cap stopped the run before this case
STATUSES = (ANSWERED, REFUSED, INVALID, ERROR, NOT_RUN)

# HTTP statuses that say the request itself is wrong (bad parameters, bad
# key, unknown model). They would repeat on every case, so they stop the run
# instead of being written down as 42 failures of the model.
FATAL_STATUS = (400, 401, 403, 404)

USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


class FatalModelError(RuntimeError):
    """The request cannot succeed on any case; the run must stop."""


def system_prompt() -> str:
    path = resources.files(__package__).joinpath("prompts/model_agent_system.txt")
    return path.read_text(encoding="utf-8")


def prompt_sha256() -> str:
    """sha256 over everything fixed that the model is sent besides the case:
    the system prompt and the tool definition."""
    blob = system_prompt() + "\n" + json.dumps(ANSWER_TOOL, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def render_case(public: dict) -> str:
    """The user message for one case, built from the public view only."""
    budget = public["budget"]
    lines = [
        f"Case {public['id']} (tier: {public['difficulty']}).",
        f"Retrieval budget: at most {budget['max_docs']} documents and "
        f"{budget['max_chars']} characters.",
        "",
        f"Question: {public['query']}",
        "",
        f"Documents ({public['n_documents']}):",
    ]
    for doc in public["documents"]:
        lines += [
            "",
            f"<document id={json.dumps(doc['id'])} source={json.dumps(doc['source'])} "
            f"published={json.dumps(doc['published'])}>",
            doc["text"],
            "</document>",
        ]
    return "\n".join(lines)


def build_request(model: str, public: dict) -> dict:
    """The exact keyword arguments of the one request an attempt sends."""
    return {
        "model": model,
        "max_tokens": SETTINGS["max_tokens"],
        "system": system_prompt(),
        "messages": [{"role": "user", "content": render_case(public)}],
        "tools": [ANSWER_TOOL],
        "tool_choice": dict(SETTINGS["tool_choice"]),
        "output_config": {"effort": SETTINGS["effort"]},
    }


def cost(usage: dict, model: str) -> float:
    """Dollars for one usage record at the model's list price."""
    price_in, price_out = PRICES[model]
    return (
        usage.get("input_tokens", 0) * price_in
        + usage.get("cache_creation_input_tokens", 0) * price_in * 1.25
        + usage.get("cache_read_input_tokens", 0) * price_in * 0.1
        + usage.get("output_tokens", 0) * price_out
    ) / 1_000_000


# The estimate has no tokenizer, so it divides characters by a number chosen
# to overstate. English prose runs near 4 characters per token on older
# tokenizers and the current one produces up to 1.35 times as many tokens,
# about 3 characters per token; 2.5 leaves margin on top of that. The fixed
# term covers the tool-use system preamble the API adds, which is not in the
# characters counted. Neither figure was checked against the API: checking
# is a network call. A run records measured tokens beside this estimate.
CHARS_PER_TOKEN = 2.5
REQUEST_OVERHEAD_TOKENS = 700


def estimate_input_tokens(request: dict) -> int:
    """An upper estimate of the input tokens one request bills."""
    chars = (
        len(request["system"])
        + sum(len(m["content"]) for m in request["messages"])
        + len(json.dumps(request["tools"]))
    )
    return int(chars / CHARS_PER_TOKEN) + REQUEST_OVERHEAD_TOKENS


def worst_case_cost(request: dict, model: str) -> float:
    """What one request can cost at most, if the input estimate holds: the
    estimated input plus max_tokens of output."""
    price_in, price_out = PRICES[model]
    tokens_in = estimate_input_tokens(request)
    return (tokens_in * price_in + request["max_tokens"] * price_out) / 1_000_000


class Budget:
    """A hard cap in dollars, checked before every request.

    A request is allowed only if what has been spent, plus the most that
    request can cost, stays within the cap. Spend is measured from the usage
    the API reports, at list prices. A request that failed without reporting
    usage (a timeout, a dropped connection) may still have been billed, so
    its worst case is held against the cap as `unmeasured`.
    """

    def __init__(self, max_usd: float) -> None:
        if not max_usd > 0:
            raise ValueError("the cap must be above 0")
        self.max_usd = float(max_usd)
        self.spent = 0.0
        self.unmeasured = 0.0
        self.stopped = False

    @property
    def committed(self) -> float:
        return self.spent + self.unmeasured

    def allows(self, worst_case: float) -> bool:
        ok = self.committed + worst_case <= self.max_usd
        if not ok:
            self.stopped = True
        return ok


@dataclass
class Outcome:
    """One case in one trial: what happened and what it cost."""

    public_id: str
    status: str
    answer: Answer | None = None
    attempts: int = 0
    usage: dict = field(default_factory=dict)
    usd: float = 0.0
    stop_reasons: list[str] = field(default_factory=list)
    detail: str = ""
    estimated_input_tokens: int = 0


# What is graded when the model gave no answer. It cites nothing and does not
# abstain, so it fails the required-citation gate on every answerable case and
# the abstention gate on every unanswerable one. tests/test_model_run.py pins
# that it fails all 42.
def failure_answer() -> Answer:
    return Answer(text="", citations=[], retrieved_ids=[], abstained=False)


def _as_dict(response: Any) -> dict:
    if isinstance(response, dict):
        return response
    return response.model_dump(mode="json", exclude_none=True)


def _usage(body: dict) -> dict:
    out = {}
    for key in USAGE_KEYS:
        value = (body.get("usage") or {}).get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            out[key] = value
    return out


def parse_tool_input(body: dict) -> Answer | str:
    """The answer in a response, or a short reason there is none."""
    blocks = body.get("content")
    if not isinstance(blocks, list):
        return "no content blocks"
    calls = [
        b for b in blocks
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == TOOL_NAME
    ]
    if len(calls) != 1:
        return f"{len(calls)} {TOOL_NAME} calls"
    data = calls[0].get("input")
    if not isinstance(data, dict):
        return "tool input is not an object"
    if set(data) != {"text", "citations", "abstained", "retrieved_ids"}:
        return f"tool input keys {sorted(data)}"
    if not isinstance(data["text"], str) or not isinstance(data["abstained"], bool):
        return "text must be a string and abstained a boolean"
    for key in ("citations", "retrieved_ids"):
        if not isinstance(data[key], list) or not all(isinstance(v, str) for v in data[key]):
            return f"{key} must be a list of strings"
    try:
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError:
        return "tool input holds text that is not valid Unicode"
    return Answer(
        text=data["text"],
        citations=list(data["citations"]),
        retrieved_ids=list(data["retrieved_ids"]),
        abstained=data["abstained"],
    )


class ModelAgent:
    """Answers public-view cases with one model through `client`.

    `client` is anything with `messages.create(**kwargs)`: an
    `anthropic.Anthropic` in a real run, a fake in the tests.
    """

    def __init__(self, model: str, client: Any, budget: Budget) -> None:
        if model not in PRICES:
            raise ValueError(f"no list price for {model!r}; known: {sorted(PRICES)}")
        self.model = model
        self.client = client
        self.budget = budget

    def answer_case(self, public: dict) -> Outcome:
        """One case. Never raises for a failure of the model or the network:
        every such failure comes back as an Outcome and is graded as a failed
        case. Raises FatalModelError when no case could succeed."""
        request = build_request(self.model, public)
        out = Outcome(
            public_id=public["id"],
            status=NOT_RUN,
            estimated_input_tokens=estimate_input_tokens(request),
        )
        reserve = worst_case_cost(request, self.model)
        for _ in range(SETTINGS["max_attempts"]):
            if not self.budget.allows(reserve):
                if out.attempts:
                    out.detail += "; cap reached before the retry"
                else:
                    out.detail = "cap reached"
                return out
            out.attempts += 1
            try:
                body = _as_dict(self.client.messages.create(**request))
            except Exception as exc:  # the SDK's own retries are already spent
                status = getattr(exc, "status_code", None)
                if status in FATAL_STATUS:
                    raise FatalModelError(
                        f"{self.model}: the API rejected the request "
                        f"({type(exc).__name__}, HTTP {status})"
                    ) from exc
                if status is None:  # no response: it may have been billed
                    self.budget.unmeasured += reserve
                out.status = ERROR
                out.detail = type(exc).__name__ + (f" HTTP {status}" if status else "")
                continue
            usage = _usage(body)
            spent = cost(usage, self.model)
            self.budget.spent += spent
            out.usd += spent
            for key, value in usage.items():
                out.usage[key] = out.usage.get(key, 0) + value
            reason = body.get("stop_reason")
            out.stop_reasons.append(str(reason))
            if reason == "refusal":
                category = (body.get("stop_details") or {}).get("category")
                out.status = REFUSED
                out.detail = f"refusal ({category})" if category else "refusal"
                return out
            parsed = parse_tool_input(body) if reason == "tool_use" else f"stop_reason {reason}"
            if isinstance(parsed, Answer):
                out.status, out.answer, out.detail = ANSWERED, parsed, ""
                return out
            out.status, out.detail = INVALID, parsed
        return out
