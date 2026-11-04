"""Mock crypto market board (read-only demo data)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Asset = Literal["BTC", "ETH", "SOL", "XRP", "DOGE", "AVAX", "LINK", "ADA"]
Window = Literal["1d", "1w", "1mo", "3mo"]

ASSETS: tuple[Asset, ...] = ("BTC", "ETH", "SOL", "XRP", "DOGE", "AVAX", "LINK", "ADA")
WINDOWS: tuple[Window, ...] = ("1d", "1w", "1mo", "3mo")


@dataclass(frozen=True)
class BoardRow:
    asset: Asset
    price: float
    returns: dict[Window, float]  # fraction, e.g. 0.012 == +1.2%
    volatility: dict[Window, float]  # annualized-ish daily vol proxy


# Deterministic mock board for demos/tests.
BOARD: dict[Asset, BoardRow] = {
    "BTC": BoardRow("BTC", 64250.0, {"1d": 0.012, "1w": 0.041, "1mo": 0.085, "3mo": 0.18}, {"1d": 0.022, "1w": 0.035, "1mo": 0.048, "3mo": 0.062}),
    "ETH": BoardRow("ETH", 3120.0, {"1d": -0.008, "1w": 0.022, "1mo": 0.055, "3mo": 0.12}, {"1d": 0.028, "1w": 0.041, "1mo": 0.055, "3mo": 0.071}),
    "SOL": BoardRow("SOL", 148.5, {"1d": 0.031, "1w": 0.09, "1mo": 0.21, "3mo": 0.45}, {"1d": 0.045, "1w": 0.062, "1mo": 0.08, "3mo": 0.11}),
    "XRP": BoardRow("XRP", 0.62, {"1d": 0.004, "1w": -0.015, "1mo": 0.03, "3mo": 0.08}, {"1d": 0.03, "1w": 0.044, "1mo": 0.058, "3mo": 0.075}),
    "DOGE": BoardRow("DOGE", 0.125, {"1d": -0.02, "1w": 0.05, "1mo": -0.04, "3mo": 0.15}, {"1d": 0.055, "1w": 0.08, "1mo": 0.1, "3mo": 0.14}),
    "AVAX": BoardRow("AVAX", 28.4, {"1d": 0.018, "1w": 0.06, "1mo": 0.11, "3mo": 0.25}, {"1d": 0.04, "1w": 0.058, "1mo": 0.072, "3mo": 0.095}),
    "LINK": BoardRow("LINK", 14.2, {"1d": 0.009, "1w": 0.028, "1mo": 0.07, "3mo": 0.16}, {"1d": 0.033, "1w": 0.05, "1mo": 0.065, "3mo": 0.085}),
    "ADA": BoardRow("ADA", 0.45, {"1d": -0.005, "1w": 0.01, "1mo": 0.04, "3mo": 0.09}, {"1d": 0.036, "1w": 0.052, "1mo": 0.068, "3mo": 0.09}),
}


def pct(x: float) -> str:
    return f"{x * 100:+.2f}%"
