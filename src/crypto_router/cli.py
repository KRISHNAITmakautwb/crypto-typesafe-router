"""CLI entrypoint: crypto-router \"show sol price\"."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crypto-router",
        description="Route natural-language crypto market commands via TypeSafe System One.",
    )
    parser.add_argument("command", help='Natural language command, e.g. "show sol price"')
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the fan-out TypeSafe questions without calling the API",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help="Path to config/spec.json (default: package config)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )
    args = parser.parse_args(argv)

    # Load .env if present (no dependency on python-dotenv)
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    from crypto_router.dispatcher import Dispatcher, load_spec
    from crypto_router.tools import TOOLS

    spec = load_spec(args.spec) if args.spec else load_spec()
    dispatcher = Dispatcher(spec=spec, tools=TOOLS)

    if args.dry_run:
        questions = dispatcher.dispatch(args.command, dry_run=True)
        if args.json:
            print(json.dumps(questions, indent=2))
        else:
            print(f"{len(questions)} questions for: {args.command!r}")
            for q in questions:
                crit = ""
                if "criteria" in q and isinstance(q["criteria"], dict):
                    crit = f"  options={list(q['criteria'])}"
                print(f"  {q['id']:<36}{q['type']:<8}{q['instructions']}{crit}")
        return 0

    if not os.environ.get("TYPESAFE_API_KEY"):
        print("TYPESAFE_API_KEY is not set. Copy .env.example to .env or export it.", file=sys.stderr)
        return 2

    result = dispatcher.dispatch(args.command)
    output = result.run(TOOLS)

    if args.json:
        payload = {
            "command": args.command,
            "call": str(result),
            "name": result.name,
            "confidence": result.confidence,
            "clarify": result.clarify,
            "kwargs": result.kwargs(),
            "output": output,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"-> {result}   confidence {result.confidence:.2f}")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
