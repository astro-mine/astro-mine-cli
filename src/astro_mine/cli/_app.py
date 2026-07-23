"""The top-level parser and process entry point.

Kept separate from ``__init__`` so the package's public surface stays a re-export list and the
argparse wiring has somewhere to grow: #2 mounts discovered subcommands onto the parser built
here, and nothing else about this module changes.

**Why the parser is built by a function rather than at import time.** ``build_parser()`` is
called per invocation, so the verb set reflects what is installed *now*. Once #2 lands discovery,
a component installed after this process started is still picked up by the next one — and, more
practically, the tests can build a parser against a fixture environment without reimporting the
module.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

__all__ = ["build_parser", "main"]

#: What ``astro-mine`` prints under its usage line. Deliberately short: the epilog carries the
#: pointer to the component CLIs, which is what a user reaching this screen actually needs.
_DESCRIPTION = "The Astro-Mine umbrella CLI — one front door to the platform's component CLIs."

#: Shown while no verbs are registered. This is the honest state of the standup release, and it
#: names the issue rather than implying the platform has no commands: every component CLI works
#: today when invoked directly, and #2 is what makes them reachable from here.
_NO_VERBS_EPILOG = (
    "No verbs are registered in this environment yet.\n"
    "\n"
    "Verb discovery (the `astro_mine.cli` entry-point group) lands in\n"
    "https://github.com/astro-mine/astro-mine-cli/issues/2. Until then, run the component CLIs\n"
    "directly — `astro-mine-bench score`, `astro-mine-sim run`, `fleet validate`, and so on.\n"
    "The naming rule they follow is conventions.md §13."
)


def build_parser() -> argparse.ArgumentParser:
    """Build the umbrella's top-level parser.

    The standup release registers no subcommands, so this is the bare shell: ``--help`` and
    ``--version``. #2 adds the subparsers, one per discovered verb.
    """
    parser = argparse.ArgumentParser(
        prog="astro-mine",
        description=_DESCRIPTION,
        epilog=_NO_VERBS_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Imported here, not at module scope: `astro_mine.cli` imports this module, so a top-level
    # import of the package would be circular.
    from astro_mine.cli import __version__

    parser.add_argument("--version", action="version", version=f"astro-mine {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the umbrella. Returns the process exit status.

    With no verbs registered, a bare ``astro-mine`` prints help and exits **0** rather than
    erroring: the user asked a dispatcher what it can do, and "nothing yet, here is why" is a
    complete answer. An *unrecognized* verb still fails through argparse (exit 2) — silence
    there would be the dishonest case.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    del args  # no subcommands to dispatch on yet (#2)
    parser.print_help()
    return 0
