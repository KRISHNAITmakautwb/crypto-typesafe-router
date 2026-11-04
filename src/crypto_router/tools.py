"""Read-only crypto market tools (no buy/sell)."""

from __future__ import annotations

from typing import Literal

from crypto_router.market import ASSETS, BOARD, Window, pct

Direction = Literal["gainers", "losers"]


def list_assets() -> str:
    return "available assets: " + ", ".join(ASSETS)


def get_price(asset: str, window: Window = "1d") -> str:
    row = BOARD[asset]  # type: ignore[index]
    return f"{asset}  {row.price:,.4g}  return({window}) {pct(row.returns[window])}"


def compare_returns(
    assets: list[str],
    window: Window = "1w",
    normalize: bool = False,
) -> str:
    if not assets:
        return "no assets selected for comparison"
    lines = [f"compare returns over {window}" + (" (normalized)" if normalize else "")]
    if normalize:
        for a in assets:
            r = BOARD[a].returns[window]  # type: ignore[index]
            lines.append(f"  {a:<5}  {100 * (1 + r):.2f}")
    else:
        ranked = sorted(assets, key=lambda a: BOARD[a].returns[window], reverse=True)  # type: ignore[index]
        for a in ranked:
            lines.append(f"  {a:<5}  {pct(BOARD[a].returns[window])}")  # type: ignore[index]
    return "\n".join(lines)


def top_movers(window: Window = "1d", direction: Direction = "gainers", limit: int = 3) -> str:
    ranked = sorted(ASSETS, key=lambda a: BOARD[a].returns[window], reverse=(direction == "gainers"))
    lines = [f"top {limit} {direction} over {window}"]
    for a in ranked[:limit]:
        row = BOARD[a]
        lines.append(f"  {a:<5}  {pct(row.returns[window])}  ->  {row.price:,.4g}")
    return "\n".join(lines)


def market_summary(window: Window = "1d") -> str:
    ranked = sorted(ASSETS, key=lambda a: BOARD[a].returns[window], reverse=True)
    lines = [f"market board over {window}"]
    for a in ranked:
        row = BOARD[a]
        lines.append(f"  {a:<5}  {row.price:>10,.4g}  {pct(row.returns[window]):>8}")
    return "\n".join(lines)


def volatility(asset: str, window: Window = "1w", annualized: bool = False) -> str:
    row = BOARD[asset]  # type: ignore[index]
    vol = row.volatility[window]
    if annualized:
        vol = vol * (365 ** 0.5)
        label = "annualized"
    else:
        label = "realized"
    return f"{asset} {label} volatility({window}) {vol * 100:.2f}%"


TOOLS = {
    "list_assets": list_assets,
    "get_price": get_price,
    "compare_returns": compare_returns,
    "top_movers": top_movers,
    "market_summary": market_summary,
    "volatility": volatility,
}
