"""Fleet's scaffold — `astro-mine new asset`.

RFC-0011 §7 puts the scaffolding *verb* in the CLI because scaffolding spans components,
and leaves the *template* with whoever owns the format. SADF is Fleet's, so the bytes are
written by :func:`astro_mine.fleet.cli._cmd_new` -- the identical handler `astro-mine fleet
new` runs. Delegating rather than re-rendering is the whole design: a second copy of the
template here would be a second SADF document to keep valid as the schema moves, and the
two would diverge silently while both still "worked".
"""

from __future__ import annotations

import argparse

from astro_mine.cli.fleet import _cmd_new

__all__ = ["asset_scaffold"]


class _AssetScaffold:
    """`astro-mine new asset <path>` — the same command as `fleet new`, reached by another road.

    RFC-0011 §7 puts the *verb* in the umbrella because scaffolding spans components, and leaves the
    *template* with whoever owns the format. SADF is Fleet's, so the bytes are written here — and
    written by :func:`astro_mine.fleet.cli._cmd_new`, the identical handler `fleet new` runs.

    **Delegating to the handler rather than re-rendering the template is the whole design.** A
    second copy of the scaffold here would be a second SADF document to keep valid as the schema
    moves, and the two would diverge silently — the umbrella's output drifting from the component's
    while both still "worked". Because this calls the same function, `astro-mine new asset` and
    `fleet new` cannot produce different bytes, and the validation `_cmd_new` already performs on
    its own output covers both paths at once.

    The argument *names* are chosen to match what that handler reads (``kind``, ``id``, ``name``,
    ``asset_version``, plus the ``output`` and ``--force`` the umbrella itself declares), so the
    parsed namespace is handed over untouched. Only the surface differs: `fleet new` takes the kind
    as a positional, and under the umbrella the first positional is already spoken for, so the kind
    becomes an option with a default. That default is what lets `astro-mine new asset rover.yaml`
    produce a valid document with nothing else typed, which is the acceptance criterion.
    """

    name = "asset"
    help = "a SADF asset (Fleet owns the format)"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.description = (
            "Scaffold a minimal, valid SADF asset. The document is validated against Core's SADF "
            "gate before it is written, so `astro-mine validate` accepts it with no hand-editing."
        )
        parser.add_argument(
            "--kind",
            default="rover",
            help="asset kind label, e.g. rover, orbiter, excavator (default: rover)",
        )
        parser.add_argument("--id", help="asset identity id (default: example.<kind>)")
        parser.add_argument("--name", help="asset display name")
        parser.add_argument(
            "--asset-version", default="0.1.0", help="asset version (default: 0.1.0)"
        )

    def run(self, args: argparse.Namespace) -> int:
        return _cmd_new(args)


asset_scaffold = _AssetScaffold()
