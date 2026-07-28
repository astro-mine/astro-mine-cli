"""Scaffold resolution — the platform's own kinds, plus anything a third party adds.

Scaffolding is a **cross-component authoring concern with no single-component home**: an asset
is Fleet's, a stack spec is Mind's, a SafetySpec is Guard's, a solver plugin is Allocate's. So
this package hosts the verbs (`astro-mine new`, `astro-mine plugin new`) and routes each kind
to its owner — the same division `validate` makes, for the same reason.

**Two sources, one shape.** The platform's 11 kinds are resolved from
:mod:`astro_mine.cli._registry`, a static table: the owning code ships in this distribution, so
asking `importlib.metadata` who provides `asset` would be a round-trip to learn something known
at author time. Third-party kinds still come from the entry-point groups, because that is the
whole no-PR-to-extend guarantee (RFC-0011 §3/§7) and it is unaffected by consolidation. Both
are wrapped in a :class:`Provider` so the verbs cannot tell them apart.

**Routing is by name, not by inspection.** Unlike `validate` — which must ask each validator
*"is this file yours?"* because a path carries no owner — the user *types the kind*
(`astro-mine new asset`). So nothing is imported to list the kinds; a scaffold's module is
imported only when that kind is actually being written.

**Two groups, not one with a flag.** Documents and plugins stay separate groups rather than one
group whose members declare which verb they belong to, because reading such a declaration would
mean loading every scaffold to render `astro-mine new --help`.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable, Mapping
from importlib.metadata import EntryPoint, entry_points
from typing import NamedTuple

from astro_mine.cli._discovery import describe_provider
from astro_mine.cli._protocol import Subcommand, check_subcommand
from astro_mine.cli._registry import DOCUMENT_KINDS, PLUGIN_KINDS, Kind

__all__ = [
    "DOCUMENT_SCAFFOLD_GROUP",
    "PLUGIN_SCAFFOLD_GROUP",
    "Provider",
    "ScaffoldCollisionError",
    "discover_scaffolds",
]

#: Authored *documents* — the things a user writes and `astro-mine validate` later checks.
#: The entry point's **name** is the kind as typed (``asset``, ``stack``, ``safety``).
DOCUMENT_SCAFFOLD_GROUP = "astro_mine.cli.scaffolds"

#: Installable *plugin packages* — a distribution registering into one of the platform's live
#: extension groups. The name is the group being written **against**, not the group it is
#: declared in.
PLUGIN_SCAFFOLD_GROUP = "astro_mine.cli.plugin_scaffolds"

_BUILTINS: dict[str, Mapping[str, Kind]] = {
    DOCUMENT_SCAFFOLD_GROUP: DOCUMENT_KINDS,
    PLUGIN_SCAFFOLD_GROUP: PLUGIN_KINDS,
}


class ScaffoldCollisionError(Exception):
    """Two providers offer the same scaffold kind.

    Held to the same stance as a verb collision, for the same reason: which package generated a
    user's starting file is provenance. A silent winner would mean `astro-mine new asset` writes
    different bytes on two machines with nothing to tell them apart — and the divergence would
    be baked into whatever the user built on top.
    """


class Provider(NamedTuple):
    """A scaffold kind's owner, whether it ships here or in somebody else's package."""

    help: str
    describe: str
    load: Callable[[], Subcommand]


def _from_registry(kind: str, spec: Kind, group: str) -> Provider:
    def load() -> Subcommand:
        module = importlib.import_module(spec.module)
        return check_subcommand(
            getattr(module, spec.attr), verb=kind, contract=group, noun="scaffold"
        )

    return Provider(help=spec.help, describe="astro-mine-cli", load=load)


def _from_entry_point(entry: EntryPoint, group: str) -> Provider:
    def load() -> Subcommand:
        # A failure *inside* the owner's import propagates unchanged, as it does for a verb:
        # turning a broken install into "unknown kind" would send the user hunting for a typo.
        return check_subcommand(
            entry.load(), verb=entry.name, entry=entry, contract=group, noun="scaffold"
        )

    return Provider(
        help=f"provided by {describe_provider(entry)}",
        describe=describe_provider(entry),
        load=load,
    )


def discover_scaffolds(
    group: str, entries: Iterable[EntryPoint] | None = None
) -> Mapping[str, Provider]:
    """Every kind available in ``group`` — **nothing is imported**.

    ``entries`` is injectable so tests can build an environment without installing packages.

    Raises :class:`ScaffoldCollisionError` if a third party claims a kind the platform owns, or
    if two third parties claim the same one.
    """
    kinds: dict[str, Provider] = {
        kind: _from_registry(kind, spec, group) for kind, spec in _BUILTINS.get(group, {}).items()
    }
    found = entry_points(group=group) if entries is None else tuple(entries)
    for entry in found:
        clash = kinds.get(entry.name)
        if clash is not None:
            raise ScaffoldCollisionError(
                f"the scaffold kind {entry.name!r} is offered by both {clash.describe} and "
                f"{describe_provider(entry)}; uninstall one, or ask the package to rename its "
                f"`{group}` entry point"
            )
        kinds[entry.name] = _from_entry_point(entry, group)
    return kinds
