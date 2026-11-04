"""Build TypeSafe questions from spec and dispatch one system_one call."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from typesafe_sdk import Choice, Noul, TypeSafeClient

ROUTE = "__tool__"
CONFIDENCE_FLOOR = 0.5


def default_spec_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "spec.json"


def load_spec(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or default_spec_path()).read_text())


def build_questions(spec: Mapping[str, Any]) -> dict[str, Choice | Noul]:
    """Fan-out: route Choice + every function's closed-set argument questions."""
    questions: dict[str, Choice | Noul] = {
        ROUTE: Choice(
            instructions=spec["route"]["question"],
            criteria=dict(spec["route"]["options"]),
        )
    }
    for fname, fspec in spec["functions"].items():
        for aname, aspec in fspec.get("arguments", {}).items():
            shape = aspec["shape"]
            if shape == "choice":
                questions[f"{fname}.{aname}"] = Choice(
                    instructions=aspec["question"],
                    criteria=dict(aspec["options"]),
                )
                if "stated" in aspec:
                    questions[f"{fname}.{aname}?"] = Noul(instructions=aspec["stated"])
            elif shape == "set":
                template = aspec["question"]
                for member, desc in aspec["options"].items():
                    q = template.replace("{}", member)
                    questions[f"{fname}.{aname}.{member}"] = Noul(
                        instructions=f"{q} ({desc})" if desc else q
                    )
            elif shape == "flag":
                questions[f"{fname}.{aname}"] = Noul(instructions=aspec["question"])
                if "stated" in aspec:
                    questions[f"{fname}.{aname}?"] = Noul(instructions=aspec["stated"])
            else:
                raise ValueError(f"unknown argument shape {shape!r} for {fname}.{aname}")
    return questions


@dataclass
class FilledArg:
    name: str
    value: Any
    probability: float
    omitted: bool = False
    distribution: dict[str, float] = field(default_factory=dict)


@dataclass
class DispatchResult:
    name: str
    arguments: dict[str, FilledArg]
    confidence: float
    tool_probability: float
    clarify: bool = False
    clarify_reason: str | None = None

    def kwargs(self) -> dict[str, Any]:
        return {k: v.value for k, v in self.arguments.items() if not v.omitted}

    def __str__(self) -> str:
        if self.clarify:
            return f"clarify({self.clarify_reason!r})"
        parts = []
        for k, v in self.arguments.items():
            if v.omitted:
                continue
            parts.append(f"{k}={v.value!r}")
        return f"{self.name}({', '.join(parts)})"

    def run(self, tools: Mapping[str, Callable[..., Any]]) -> Any:
        if self.clarify:
            return f"Please clarify: {self.clarify_reason}"
        if self.name == "none":
            return (
                "I only answer read-only market questions "
                "(prices, returns, movers, volatility). No buy/sell."
            )
        fn = tools[self.name]
        return fn(**self.kwargs())


def _choice_answer(response: Any, qid: str) -> Any:
    if hasattr(response, "choices") and qid in response.choices:
        return response.choices[qid]
    answers = getattr(response, "answers", None)
    if answers is not None and qid in answers:
        return answers[qid]
    raise KeyError(qid)


def _noul_answer(response: Any, qid: str) -> Any:
    if hasattr(response, "nouls") and qid in response.nouls:
        return response.nouls[qid]
    answers = getattr(response, "answers", None)
    if answers is not None and qid in answers:
        return answers[qid]
    raise KeyError(qid)


def _prob(ans: Any) -> float:
    if hasattr(ans, "probability") and ans.probability is not None:
        return float(ans.probability)
    # Choice: use top probability from distribution if present
    probs = getattr(ans, "probabilities", None)
    if isinstance(probs, dict) and probs:
        return float(max(probs.values()))
    noul = getattr(ans, "noul", None)
    if noul is not None:
        # treat yes-probability distance from 0.5 as certainty proxy for gates
        return float(max(noul, 1.0 - noul))
    conf = getattr(ans, "confidence", None)
    if conf is not None:
        return float(conf)
    return 1.0


def _confidence(ans: Any) -> float:
    conf = getattr(ans, "confidence", None)
    if conf is not None:
        return float(conf)
    return _prob(ans)


def fill_arguments(
    spec: Mapping[str, Any],
    tool: str,
    response: Any,
) -> tuple[dict[str, FilledArg], list[float]]:
    """Fill closed-set args for the chosen tool; omit unstated optionals."""
    filled: dict[str, FilledArg] = {}
    used: list[float] = []
    if tool == "none" or tool not in spec["functions"]:
        return filled, used

    for aname, aspec in spec["functions"][tool].get("arguments", {}).items():
        shape = aspec["shape"]
        stated_id = f"{tool}.{aname}?"
        if "stated" in aspec:
            stated = _noul_answer(response, stated_id)
            stated_p = float(getattr(stated, "noul", 0.0))
            used.append(_confidence(stated) if hasattr(stated, "confidence") else max(stated_p, 1 - stated_p))
            if stated_p < 0.5:
                filled[aname] = FilledArg(aname, None, stated_p, omitted=True)
                continue

        if shape == "choice":
            ans = _choice_answer(response, f"{tool}.{aname}")
            choice = getattr(ans, "choice", None)
            probs = dict(getattr(ans, "probabilities", {}) or {})
            conf = _confidence(ans)
            used.append(conf)
            filled[aname] = FilledArg(aname, choice, conf, omitted=False, distribution=probs)
        elif shape == "set":
            members: list[str] = []
            dist: dict[str, float] = {}
            worst = 1.0
            for member in aspec["options"]:
                ans = _noul_answer(response, f"{tool}.{aname}.{member}")
                p = float(getattr(ans, "noul", 0.0))
                dist[member] = p
                # only members judged present contribute to confidence
                if p >= 0.5:
                    members.append(member)
                    worst = min(worst, max(p, 1 - p))
            if members:
                used.append(worst)
            filled[aname] = FilledArg(aname, members, worst if members else 1.0, omitted=False, distribution=dist)
        elif shape == "flag":
            ans = _noul_answer(response, f"{tool}.{aname}")
            p = float(getattr(ans, "noul", 0.0))
            used.append(max(p, 1 - p))
            filled[aname] = FilledArg(aname, p >= 0.5, max(p, 1 - p), omitted=False)
    return filled, used


class Dispatcher:
    def __init__(
        self,
        spec: Mapping[str, Any] | None = None,
        tools: Mapping[str, Callable[..., Any]] | None = None,
        client: TypeSafeClient | None = None,
        model: str | None = "jev",
        confidence_floor: float = CONFIDENCE_FLOOR,
    ) -> None:
        from crypto_router.tools import TOOLS

        self.spec = dict(spec or load_spec())
        self.tools = dict(tools or TOOLS)
        self.client = client
        self.model = model
        self.confidence_floor = confidence_floor
        self.questions = build_questions(self.spec)

    def describe_questions(self) -> list[dict[str, Any]]:
        out = []
        for qid, q in self.questions.items():
            item: dict[str, Any] = {"id": qid, "type": type(q).__name__}
            item["instructions"] = getattr(q, "instructions", None)
            criteria = getattr(q, "criteria", None)
            if criteria is not None:
                item["criteria"] = criteria
            out.append(item)
        return out

    def dispatch(self, command: str, *, dry_run: bool = False) -> DispatchResult | list[dict[str, Any]]:
        if dry_run:
            return self.describe_questions()

        if self.client is None:
            self.client = TypeSafeClient()

        kwargs: dict[str, Any] = {
            "state": {"command": command},
            "questions": self.questions,
        }
        if self.model:
            kwargs["model"] = self.model
        response = self.client.system_one(**kwargs)

        route = _choice_answer(response, ROUTE)
        tool = getattr(route, "choice", None)
        tool_p = _prob(route)
        tool_conf = _confidence(route)

        if tool is None:
            return DispatchResult(
                name="none",
                arguments={},
                confidence=0.0,
                tool_probability=0.0,
                clarify=True,
                clarify_reason="could not route the command",
            )

        filled, used_confs = fill_arguments(self.spec, tool, response)
        confidences = [tool_conf, *used_confs]
        confidence = min(confidences) if confidences else tool_conf

        if confidence < self.confidence_floor:
            return DispatchResult(
                name=tool,
                arguments=filled,
                confidence=confidence,
                tool_probability=tool_p,
                clarify=True,
                clarify_reason=(
                    f"low confidence ({confidence:.2f}) routing to {tool}; "
                    "please rephrase with asset and window"
                ),
            )

        return DispatchResult(
            name=tool,
            arguments=filled,
            confidence=confidence,
            tool_probability=tool_p,
        )

    def __call__(self, command: str, *, dry_run: bool = False) -> DispatchResult | list[dict[str, Any]]:
        return self.dispatch(command, dry_run=dry_run)
