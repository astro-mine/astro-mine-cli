"""The built-in scaffolding verbs — `astro-mine new` and `astro-mine plugin new` (RFC-0011 §7).

Both are **routers**, like `validate` and for the same reason: the thing being written belongs to a
component, but deciding *which* component belongs to nobody but the umbrella. `astro-mine new
asset` is Fleet's document; `astro-mine plugin new solver` is Allocate's extension group; neither
package can host the verb without knowing about the other seven.

**A second turn of the same crank.** The top level parses only *which verb* and leaves the tail
alone so it can import one component instead of all of them
(:mod:`astro_mine.cli._dispatch`). These verbs repeat that exactly one level down: parse only
*which kind*, load that one scaffold, and let it parse its own tail. `astro-mine new` with no kind
lists what is available without importing anything at all.

**The umbrella owns two arguments, and only two.** It declares ``output`` and ``--force`` before
handing the parser to a scaffold, so `astro-mine new <anything>` has the same skeleton and a user
who has scaffolded one kind can scaffold the next without re-reading the help. Everything else is
the owner's to declare; a scaffold must not re-declare those two.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from importlib.metadata import EntryPoint, PackageNotFoundError, version
from types import MappingProxyType

from astro_mine.cli._protocol import InvalidSubcommandError, Subcommand
from astro_mine.cli._scaffolds import (
    DOCUMENT_SCAFFOLD_GROUP,
    PLUGIN_SCAFFOLD_GROUP,
    Provider,
    ScaffoldCollisionError,
    discover_scaffolds,
)
from astro_mine.cli._templates import CLI_PLUGIN_SCAFFOLD

__all__ = ["new", "plugin"]

_USAGE_ERROR = 2

#: What a user types to ask for help. Spelled out because `plugin new`'s tail is an
#: :data:`argparse.REMAINDER`, which hands these through verbatim instead of acting on them.
_HELP_FLAGS = frozenset({"-h", "--help"})

#: `new` has no built-in kinds — every document belongs to a component. Only `plugin new` does,
#: and only one (see :mod:`astro_mine.cli._templates`).
_NO_BUILTINS: Mapping[str, Subcommand] = MappingProxyType({})


class _Scaffolder:
    """The shared body of both verbs: list kinds, or route one kind to its owner.

    Parameterized by group rather than duplicated, because the two verbs now differ in exactly
    two things -- the group they read and the words in their messages.

    **The degradation machinery is gone.** This class used to carry a static kind→distribution
    table so it could answer *"`astro-mine new stack` needs astro-mine-mind — pip install it"*,
    and a second branch for *"that component is installed but offers no scaffold"*. Neither
    state can occur now: every first-party kind ships in this distribution's own
    :mod:`astro_mine.cli.scaffolds`, so a kind is either present or genuinely misspelled.
    """

    def __init__(
        self,
        *,
        command: str,
        group: str,
        builtins: Mapping[str, Subcommand] = _NO_BUILTINS,
        noun: str = "kind",
    ) -> None:
        self.command = command
        self.group = group
        self.builtins = builtins
        self.noun = noun

    def dispatch(self, kind: str, rest: list[str]) -> int:
        """Load the one scaffold that owns ``kind`` and hand it the rest of the command line."""
        try:
            available = self._available()
        except ScaffoldCollisionError as exc:
            print(f"astro-mine {self.command}: {exc}", file=sys.stderr)
            return _USAGE_ERROR

        scaffold = self.builtins.get(kind)
        if scaffold is None:
            provider = available.get(kind)
            if provider is None:
                return self._report_unknown(kind, available)
            try:
                scaffold = provider.load()
            except InvalidSubcommandError as exc:
                print(f"astro-mine {self.command}: {exc}", file=sys.stderr)
                return _USAGE_ERROR

        parser = argparse.ArgumentParser(
            prog=f"astro-mine {self.command} {kind}", description=scaffold.help
        )
        parser.add_argument("output", help="path to write to")
        parser.add_argument("--force", action="store_true", help="overwrite what is already there")
        scaffold.add_arguments(parser)
        status = scaffold.run(parser.parse_args(rest))
        return 0 if status is None else int(status)

    def _available(self) -> Mapping[str, Provider]:
        """Every kind this environment offers, first-party and third-party alike."""
        discovered = dict(discover_scaffolds(self.group))
        shadowed = sorted(set(discovered) & set(self.builtins))
        if shadowed:
            raise ScaffoldCollisionError(
                f"{', '.join(repr(k) for k in shadowed)} shadows a {self.noun} this CLI owns; "
                f"uninstall the package or ask it to rename its `{self.group}` entry point"
            )
        return discovered

    def listing(self) -> str:
        """What `astro-mine <command>` prints with no kind — built without importing a scaffold."""
        available = self._available()
        names = sorted({*available, *self.builtins})
        width = max((len(k) for k in names), default=0) + 2
        lines = [f"usage: astro-mine {self.command} <{self.noun}> <output> [options]", ""]
        lines.append(f"{self.noun.title()}s:")
        lines += [f"  {kind:<{width}}{self._summarize(kind, available)}" for kind in names]
        lines += ["", f"`astro-mine {self.command} <{self.noun}> --help` shows its own options."]
        return "\n".join(lines)

    def _summarize(self, kind: str, available: Mapping[str, Provider]) -> str:
        """One line about a kind — never from the scaffold itself: that would cost an import."""
        builtin = self.builtins.get(kind)
        return builtin.help if builtin is not None else available[kind].help

    def _report_unknown(self, kind: str, available: Mapping[str, Provider]) -> int:
        """A kind nobody offers. With every component present, that is a typo -- so say so."""
        import difflib

        names = sorted({*available, *self.builtins})
        close = difflib.get_close_matches(kind, names, n=1)
        hint = f" (did you mean {close[0]!r}?)" if close else ""
        print(
            f"astro-mine {self.command}: unknown {self.noun} {kind!r}{hint}; "
            f"available: {', '.join(names)}",
            file=sys.stderr,
        )
        return _USAGE_ERROR


class _New:
    name = "new"
    help = "scaffold an authored document (routed to the format's owner)"

    _scaffolder = _Scaffolder(command="new", group=DOCUMENT_SCAFFOLD_GROUP)

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.description = (
            "Scaffold an authored document. Each kind is written by the component that owns its "
            "format; this command owns no schema of its own (RFC-0011 §7). What it writes is "
            "valid on arrival — `astro-mine validate` accepts it with no hand-editing."
        )
        parser.add_argument("kind", nargs="?", help="what to scaffold; omit to list the kinds")
        parser.add_argument(
            "rest",
            nargs=argparse.REMAINDER,
            help="arguments for the kind (`astro-mine new <kind> --help` for its own help)",
        )

    def run(self, args: argparse.Namespace) -> int:
        if args.kind is None:
            print(self._scaffolder.listing())
            return 0
        return self._scaffolder.dispatch(args.kind, args.rest)


class _Plugin:
    """`astro-mine plugin new <kind>` — one verb with one action, per RFC-0011 §2's surface.

    ``new`` is spelled out rather than folded into `astro-mine new`, because a plugin and a
    document are different things: one is an installable distribution that extends the platform,
    the other is a file the platform reads. Collapsing them would make `astro-mine new solver`
    write a Python package while `astro-mine new asset` writes YAML, from the same word.
    """

    name = "plugin"
    help = "scaffold a plugin package (`plugin new <kind>`)"

    _scaffolder = _Scaffolder(
        command="plugin new",
        group=PLUGIN_SCAFFOLD_GROUP,
        builtins={CLI_PLUGIN_SCAFFOLD.name: CLI_PLUGIN_SCAFFOLD},
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.description = (
            "Author a plugin against one of the platform's live extension groups. The recipes "
            "these scaffolds emit are the ones in the plugin-authoring guide "
            "(guide/how-to/write-a-plugin.md)."
        )
        parser.add_argument("action", nargs="?", help="`new` — scaffold a plugin package")
        parser.add_argument("rest", nargs=argparse.REMAINDER, help="`<kind> <output> [options]`")

    def run(self, args: argparse.Namespace) -> int:
        if args.action is None:
            print(self._scaffolder.listing())
            return 0
        if args.action != "new":
            print(
                f"astro-mine plugin: unknown action {args.action!r} (available: new)",
                file=sys.stderr,
            )
            return _USAGE_ERROR
        # `--help` is claimed here rather than by argparse, because REMAINDER stops option
        # processing: without this the flag arrives as the kind positional and comes back as
        # `unknown kind '--help'`, which reads as the tool being confused about the most standard
        # flag there is. `astro-mine new --help` prints help and exits 0; so does this.
        if not args.rest or args.rest[0] in _HELP_FLAGS:
            print(self._scaffolder.listing())
            return 0
        return self._scaffolder.dispatch(args.rest[0], args.rest[1:])


new = _New()
plugin = _Plugin()
