"""Snapshot every pre-change component parser as a structured fixture.

Run against astro-mine-platform BEFORE any CLI module is deleted. The output is the
parity contract astro-mine-cli's tests assert against: for all 50 verbs, the complete
argparse specification (options, defaults, nargs, choices, required, help).

`prog` is deliberately normalized away -- `astro-mine-bench score` legitimately becomes
`astro-mine bench score`. Everything else must match exactly.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from typing import Any

# component -> (module, builder attr or None to intercept main())
SOURCES: dict[str, tuple[str, str | None]] = {
    "core": ("astro_mine.core.cli", "_build_parser"),
    "sim": ("astro_mine.sim.__main__", "_build_parser"),
    "bench": ("astro_mine.bench.cli", "_build_parser"),
    "hub": ("astro_mine.hub.client.cli", "_parser"),
    "fleet": ("astro_mine.fleet.cli", "_build_parser"),
    "worlds": ("astro_mine.worlds.cli", "_build_parser"),
    "link": ("astro_mine.link.cli", None),
    "prospect": ("astro_mine.prospect.publish._publish", None),
    "mind": ("astro_mine.mind.cli", "_build_parser"),
    "guard": ("astro_mine.guard.cli", "_build_parser"),
    "studio": ("astro_mine.studio.cli", "_build_parser"),
    "cloud": ("astro_mine.cloud.submission.cli", "_build_parser"),
    "learn": ("astro_mine.learn.train.run", "_parser"),
}


class _Captured(Exception):
    def __init__(self, parser: argparse.ArgumentParser) -> None:
        self.parser = parser


def _capture_via_main(module: Any) -> argparse.ArgumentParser:
    """Modules that build their parser inline in main(): intercept parse_args."""
    original = argparse.ArgumentParser.parse_args

    def spy(self: argparse.ArgumentParser, *a: Any, **k: Any) -> Any:
        raise _Captured(self)

    argparse.ArgumentParser.parse_args = spy  # type: ignore[method-assign]
    try:
        module.main([])
    except _Captured as caught:
        return caught.parser
    finally:
        argparse.ArgumentParser.parse_args = original  # type: ignore[method-assign]
    raise RuntimeError("parser was never captured")


def _describe_action(action: argparse.Action) -> dict[str, Any]:
    type_ = action.type
    return {
        "cls": type(action).__name__,
        "option_strings": sorted(action.option_strings),
        "dest": action.dest,
        "nargs": action.nargs,
        "const": repr(action.const) if action.const is not None else None,
        "default": repr(action.default),
        "type": getattr(type_, "__name__", None) or (repr(type_) if type_ else None),
        "choices": sorted(map(str, action.choices)) if action.choices else None,
        "required": action.required,
        "help": action.help,
        "metavar": action.metavar,
    }


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _describe(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """One parser: its own options (minus the subparser action), then its verbs."""
    subs = _subparsers(parser)
    own = [
        _describe_action(a)
        for a in parser._actions
        if not isinstance(a, argparse._SubParsersAction | argparse._HelpAction)
    ]
    own.sort(key=lambda d: (d["dest"], ",".join(d["option_strings"])))
    return {
        "description": (parser.description or "").strip(),
        "actions": own,
        "verbs": {name: _describe(sub) for name, sub in sorted(subs.items())},
    }


def main() -> int:
    snapshot: dict[str, Any] = {}
    for component, (module_path, builder) in SOURCES.items():
        module = importlib.import_module(module_path)
        parser = getattr(module, builder)() if builder else _capture_via_main(module)
        snapshot[component] = _describe(parser)
        verbs = snapshot[component]["verbs"]
        print(f"{component:9} {len(verbs) or '-':>2} verbs", file=sys.stderr)

    total = sum(len(c["verbs"]) or 1 for c in snapshot.values())
    print(f"\ntotal: {total} verbs across {len(snapshot)} components", file=sys.stderr)
    json.dump(snapshot, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
