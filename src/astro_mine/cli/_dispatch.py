"""The root parser and the dispatch loop — `astro-mine <component> <verb>`.

**One grammar.** Every command the platform ships is addressed the same way: the component
that owns it, then the verb. The only exceptions are the three *routers* — ``validate``,
``new`` and ``plugin new`` — which exist precisely because deciding which component owns a
document or a kind is the one job no component can do for itself.

Before this package depended on the platform there were three addressing rules at once:
eight components reachable as a passthrough, four with selected verbs promoted to the top
level, and one (`core`) not reachable at all — so `astro-mine core validate`, `hub resolve`,
`bench zoo-sync` and `worlds schema` simply could not be typed. One root, one grammar
(astro-mine-cli#12).

**Why parsing still happens in two phases.** Filling in a component's arguments means
importing that component's CLI module, which imports the platform package behind it. A
single-phase parser would import all fourteen just to render ``--help``. So phase one parses
only *which* component (everything after it is :data:`argparse.REMAINDER`), and phase two
imports that one module and lets it parse its own tail. The user pays for the command they
ran and nothing else — the one property of RFC-0011 §1a worth carrying past consolidation.

The cost is that top-level ``--help`` cannot show a component's own verbs. That is what
:mod:`astro_mine.cli._registry` is for: the descriptions are static strings, so the listing
stays free, and the real help comes from ``astro-mine <component> --help``.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Mapping, Sequence
from importlib.metadata import EntryPoint

from astro_mine.cli._discovery import (
    VerbCollisionError,
    describe_provider,
    discover_verbs,
    load_verb,
)
from astro_mine.cli._new import new as _new_verb
from astro_mine.cli._new import plugin as _plugin_verb
from astro_mine.cli._protocol import InvalidSubcommandError, Subcommand
from astro_mine.cli._registry import COMPONENTS
from astro_mine.cli._validate import validate as _validate_verb

__all__ = ["build_parser", "main"]

_DESCRIPTION = (
    "The Astro-Mine CLI — one front door to the platform: `astro-mine <component> <verb>`."
)

#: Exit status for a usage error, matching argparse's own convention. Kept distinct from the
#: 1-and-up range a command uses for its *own* failures, so a script can tell "I typed this
#: wrong" from "the run failed".
_USAGE_ERROR = 2

#: The three verbs this package owns outright. All three *route* rather than do, and routing
#: is the one job no component can hold without importing its siblings (`conventions.md §1.1`).
#: `validate` sends a document to whoever owns its format (RFC-0011 §6); `new` and `plugin new`
#: send a scaffold request to whoever owns the kind (§7). Nothing else belongs here — a verb
#: that *does* something belongs to the component that does it, under that component's name.
_ROUTERS: dict[str, Subcommand] = {
    verb.name: verb for verb in (_validate_verb, _new_verb, _plugin_verb)
}


def build_parser(verbs: Mapping[str, EntryPoint] | None = None) -> argparse.ArgumentParser:
    """Build the phase-one parser: the component (or router), and the rest untouched.

    ``verbs`` is the third-party set, injectable for tests; ``None`` reads the environment.
    Threading it through rather than re-discovering inside :func:`_format_listing` matters:
    the listing must describe the same environment the dispatcher will route in, or a caller
    that injected a verb would be told it does not exist and then have it work anyway.
    """
    parser = argparse.ArgumentParser(
        prog="astro-mine",
        description=_DESCRIPTION,
        epilog=_format_listing(verbs),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
    )
    from astro_mine.cli import __version__

    parser.add_argument("--version", action="version", version=f"astro-mine {__version__}")
    parser.add_argument("name", nargs="?", help="a component or a router; see the list below")
    # REMAINDER, not a subparser tree: the tail belongs to the component's own parser, which
    # does not exist until that component is imported. It also means this package never has
    # to mirror — and drift from — a component's flags.
    parser.add_argument(
        "rest",
        nargs=argparse.REMAINDER,
        help="arguments for the component or router "
        "(`astro-mine <component> --help` for its own help)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    verbs: Mapping[str, EntryPoint] | None = None,
) -> int:
    """Run the CLI. Returns the process exit status.

    A bare ``astro-mine`` prints help and exits **0** — the user asked a dispatcher what it
    can do, and the listing is a complete answer.

    A broken *environment* — a third-party package claiming a name the platform owns, or a
    provider that does not satisfy the contract — is reported as a message and a non-zero
    status, never as a traceback: both are somebody else's packaging bug, and a stack trace
    through this package would point every reader at the wrong repo. A failure *inside* a
    command is not caught; that belongs to the component, and swallowing it would hide real
    errors.
    """
    try:
        third_party = discover_verbs() if verbs is None else verbs
    except VerbCollisionError as exc:
        print(f"astro-mine: {exc}", file=sys.stderr)
        return _USAGE_ERROR

    reserved = set(COMPONENTS) | set(_ROUTERS)
    shadowed = sorted(set(third_party) & reserved)
    if shadowed:
        names = ", ".join(f"{v!r} ({describe_provider(third_party[v])})" for v in shadowed)
        print(
            f"astro-mine: {names} shadows a name the platform owns; uninstall the package or "
            f"ask it to rename its `astro_mine.cli` entry point",
            file=sys.stderr,
        )
        return _USAGE_ERROR

    parser = build_parser(third_party)
    args = parser.parse_args(argv)

    if args.name is None:
        parser.print_help()
        return 0

    try:
        subcommand = _resolve(args.name, third_party)
    except InvalidSubcommandError as exc:
        print(f"astro-mine: {exc}", file=sys.stderr)
        return _USAGE_ERROR
    if subcommand is None:
        return _report_unknown(parser, args.name, third_party)

    sub = argparse.ArgumentParser(
        prog=f"astro-mine {args.name}",
        description=subcommand.help,
    )
    subcommand.add_arguments(sub)
    status = subcommand.run(sub.parse_args(args.rest))
    # `None` is the near-universal Python convention for "finished, no error" (it is what
    # sys.exit(None) means); a command that ran fine should not be punished for following it.
    return 0 if status is None else int(status)


def _resolve(name: str, third_party: Mapping[str, EntryPoint]) -> Subcommand | None:
    """Find who handles ``name`` — router, component, or third-party verb, in that order.

    The order is also the precedence, and it is not negotiable: the two first-party sets are
    checked before installed metadata so a third-party package cannot silently take over a
    platform name. (It cannot reach here anyway — ``main`` rejects the collision first — but
    resolution should not depend on that check having run.)
    """
    router = _ROUTERS.get(name)
    if router is not None:
        return router

    component = COMPONENTS.get(name)
    if component is not None:
        module = importlib.import_module(component.module)
        return module.command  # type: ignore[no-any-return]

    entry = third_party.get(name)
    return None if entry is None else load_verb(entry)


def _report_unknown(
    parser: argparse.ArgumentParser, name: str, third_party: Mapping[str, EntryPoint]
) -> int:
    """A name nobody claims. Suggest the nearest real one before giving the full list.

    The old umbrella had a static verb→distribution table here, so it could answer "that verb
    needs a package you have not installed". In one distribution that case cannot arise —
    every component is present — so an unrecognized name is a genuine mistake, and the useful
    reply is the closest thing the user might have meant.
    """
    import difflib

    known = sorted({*COMPONENTS, *_ROUTERS, *third_party})
    close = difflib.get_close_matches(name, known, n=1)
    hint = f" (did you mean {close[0]!r}?)" if close else ""
    parser.error(f"unknown component or verb {name!r}{hint}; available: {', '.join(known)}")


def _format_listing(verbs: Mapping[str, EntryPoint] | None = None) -> str:
    """The listing under ``--help``, built without importing a single component."""
    width = max(len(n) for n in (*COMPONENTS, *_ROUTERS)) + 2
    lines = ["Components — `astro-mine <component> <verb>`:"]
    lines += [f"  {name:<{width}}{spec.help}" for name, spec in COMPONENTS.items()]
    lines += ["", "Routers — these pick the owning component for you:"]
    lines += [f"  {name:<{width}}{verb.help}" for name, verb in _ROUTERS.items()]

    if verbs is None:
        try:
            verbs = discover_verbs()
        except VerbCollisionError:
            verbs = {}
    installed = {n: e for n, e in verbs.items() if n not in {*COMPONENTS, *_ROUTERS}}
    if installed:
        lines += ["", "Added by installed packages:"]
        lines += [f"  {n:<{width}}provided by {describe_provider(e)}" for n, e in installed.items()]

    lines += ["", "`astro-mine <component> --help` lists that component's verbs."]
    return "\n".join(lines)
