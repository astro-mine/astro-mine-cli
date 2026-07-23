"""Astro-Mine-CLI — the discoverable umbrella CLI.

One command, ``astro-mine <verb>``, in front of a platform that ships a CLI per component. A
user who does not yet know which package owns an action can guess the *action* and find it:
``astro-mine score``, ``astro-mine fetch``, ``astro-mine train``. Every component CLI keeps
working when invoked directly — the umbrella is the discoverable entry, **not** a replacement
(`RFC-0011 <https://github.com/astro-mine/docs/blob/main/rfc/0011-umbrella-cli.md>`_;
``conventions.md §13``, normative).

**What this package is allowed to be.** A near-zero-dependency dispatcher: argparse and the
stdlib, and no runtime dependency on any Astro-Mine package — not even Core. RFC-0011 rejected
the umbrella-that-depends-on-everything because installing it to get one verb would drag the
whole platform onto the machine and break the local tier that must always work
(``conventions.md §7``). Verbs are discovered from the **``astro_mine.cli``** entry-point group,
so a component — or a third party — contributes one by declaring an entry point, never by a PR
to this package.

**This release (the repo standup, #1) is the shell only.** The parser, the console script, the
packaging rules and the CI lane that holds them are here; discovery, the first-party manifest,
the ``Subcommand`` protocol and honest degradation land in #2. Until then ``astro-mine --help``
runs and truthfully reports that no verbs are registered — which is the correct output for a
dispatcher with nothing to dispatch to, not an error.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from astro_mine.cli._app import build_parser, main

__all__ = ["__version__", "build_parser", "main"]

try:
    __version__ = version("astro-mine-cli")
except PackageNotFoundError:  # pragma: no cover - source checkout without an install
    __version__ = "0.0.0.dev0"
