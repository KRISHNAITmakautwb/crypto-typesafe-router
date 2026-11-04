"""Unit tests with a mocked TypeSafeClient."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from crypto_router.dispatcher import ROUTE, Dispatcher, build_questions, load_spec
from crypto_router.tools import TOOLS, get_price, list_assets


class FakeChoice:
    def __init__(self, choice: str, confidence: float = 0.9, probabilities: dict | None = None):
        self.choice = choice
        self.confidence = confidence
        self.probabilities = probabilities or {choice: confidence}
        self.probability = self.probabilities.get(choice, confidence)


class FakeNoul:
    def __init__(self, noul: float):
        self.noul = noul


class FakeResponse:
    def __init__(self, choices: dict, nouls: dict):
        self.choices = choices
        self.nouls = nouls
        self.answers = {**choices, **nouls}


class FakeClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict] = []

    def system_one(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def spec():
    return load_spec()


def test_build_questions_includes_route_and_none(spec):
    qs = build_questions(spec)
    assert ROUTE in qs
    assert "none" in spec["route"]["options"]
    # fan-out: one call worth of questions for all tools
    assert any(k.startswith("get_price.asset") for k in qs)
    assert any(k.startswith("compare_returns.assets.") for k in qs)
    assert "get_price.window?" in qs  # stated gate for optional


def test_list_assets_tool():
    assert "BTC" in list_assets()
    assert "SOL" in list_assets()


def test_get_price_tool():
    out = get_price("SOL", window="1d")
    assert out.startswith("SOL")


def test_dispatch_get_price(spec):
    response = FakeResponse(
        choices={
            ROUTE: FakeChoice("get_price", 0.95),
            "get_price.asset": FakeChoice("SOL", 0.92, {"SOL": 0.92, "BTC": 0.05}),
            "get_price.window": FakeChoice("1d", 0.8),
        },
        nouls={
            "get_price.window?": FakeNoul(0.1),  # unstated -> omit
        },
    )
    client = FakeClient(response)
    d = Dispatcher(spec=spec, tools=TOOLS, client=client)
    result = d("show sol price")
    assert result.clarify is False
    assert result.name == "get_price"
    assert result.kwargs() == {"asset": "SOL"}
    assert "window" not in result.kwargs()  # omitted optional
    assert "SOL" in result.run(TOOLS)
    assert len(client.calls) == 1
    assert ROUTE in client.calls[0]["questions"]


def test_confidence_gate(spec):
    response = FakeResponse(
        choices={
            ROUTE: FakeChoice("get_price", confidence=0.3, probabilities={"get_price": 0.4, "none": 0.35}),
            "get_price.asset": FakeChoice("BTC", 0.4),
            "get_price.window": FakeChoice("1d", 0.5),
        },
        nouls={"get_price.window?": FakeNoul(0.2)},
    )
    d = Dispatcher(spec=spec, tools=TOOLS, client=FakeClient(response))
    result = d("hmm price maybe")
    assert result.clarify is True
    assert result.confidence < 0.5


def test_dry_run_no_api(spec):
    class Boom:
        def system_one(self, **kwargs):
            raise AssertionError("API should not be called")

    d = Dispatcher(spec=spec, tools=TOOLS, client=Boom())  # type: ignore[arg-type]
    questions = d("show sol price", dry_run=True)
    assert isinstance(questions, list)
    assert any(q["id"] == ROUTE for q in questions)


def test_none_route(spec):
    response = FakeResponse(
        choices={ROUTE: FakeChoice("none", 0.9)},
        nouls={},
    )
    d = Dispatcher(spec=spec, tools=TOOLS, client=FakeClient(response))
    result = d("buy 2 eth")
    assert result.name == "none"
    out = result.run(TOOLS)
    assert "buy/sell" in out.lower() or "read-only" in out.lower()


def test_compare_returns_set(spec):
    nouls = {
        **{f"compare_returns.assets.{a}": FakeNoul(0.9 if a in ("BTC", "ETH") else 0.05)
           for a in spec["functions"]["compare_returns"]["arguments"]["assets"]["options"]},
        "compare_returns.window?": FakeNoul(0.9),
        "compare_returns.normalize?": FakeNoul(0.1),
        "compare_returns.normalize": FakeNoul(0.1),
    }
    response = FakeResponse(
        choices={
            ROUTE: FakeChoice("compare_returns", 0.95),
            "compare_returns.window": FakeChoice("1w", 0.9),
        },
        nouls=nouls,
    )
    d = Dispatcher(spec=spec, tools=TOOLS, client=FakeClient(response))
    result = d("compare btc and eth this week")
    assert result.name == "compare_returns"
    assert set(result.kwargs()["assets"]) == {"BTC", "ETH"}
    assert result.kwargs()["window"] == "1w"
    assert "normalize" not in result.kwargs() or result.kwargs().get("normalize") is False
