"""The static first-party tables — plain strings, no imports, no platform.

Every name a user can type at the top level is listed here, together with the module that
implements it and one line of help. Nothing in this module imports anything: that is the
whole point of it existing.

**Why a table and not discovery.** Before consolidation the umbrella federated first-party
commands through the ``astro_mine.cli`` entry-point group, because a component might not be
installed and the umbrella was forbidden from depending on one (RFC-0011 §1a). Neither
premise survives: this package depends on ``astro-mine-platform``, so every component is
present, and metadata round-trips buy nothing but a slower start and an indirection that
hides which function runs. First-party dispatch is therefore static. Entry points remain
exactly where they still earn their keep — third-party extension (:mod:`._discovery`,
:mod:`._validators`, :mod:`._scaffolds`).

**Why strings and not imports.** ``astro-mine --help`` must render the whole platform
without importing any of it. A table of module *paths* lets the dispatcher list 16 names for
free and import exactly one — the command the user actually typed. The tests assert the
negative (no ``astro_mine.<component>`` in ``sys.modules`` after a help run), because a
stray convenience import is invisible until someone measures startup.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import NamedTuple

__all__ = [
    "COMPONENTS",
    "DOCUMENT_KINDS",
    "PLUGIN_KINDS",
    "VALIDATOR_OWNERS",
    "Component",
    "Kind",
]


class Component(NamedTuple):
    """One ``astro-mine <component> …`` group: where it lives, and what it is for."""

    module: str
    help: str


#: The 13 components that ship commands, in the order a user meets them: author content,
#: run it, score it, train, publish, then the surfaces that orchestrate. `spice`, `seal`,
#: `surrogate` and `allocate` expose no commands and get no group; they gain one the day
#: they do. (`allocate` still owns the `solver` plugin scaffold — that reaches users through
#: `astro-mine plugin new solver`, which is routed by kind, not by component.)
COMPONENTS: MappingProxyType[str, Component] = MappingProxyType(
    {
        "core": Component("astro_mine.cli.core", "validate Core-authored formats; list them"),
        "fleet": Component("astro_mine.cli.fleet", "author, package and publish SADF assets"),
        "worlds": Component("astro_mine.cli.worlds", "author and publish world bundles"),
        "prospect": Component("astro_mine.cli.prospect", "publish resource priors"),
        "link": Component("astro_mine.cli.link", "publish contact plans"),
        "sim": Component("astro_mine.cli.sim", "run and record simulated episodes"),
        "bench": Component("astro_mine.cli.bench", "fetch, score and submit benchmark runs"),
        "learn": Component("astro_mine.cli.learn", "train a policy and export it"),
        "mind": Component("astro_mine.cli.mind", "validate and compose autonomy stacks"),
        "guard": Component("astro_mine.cli.guard", "author, compile and falsify SafetySpecs"),
        "hub": Component("astro_mine.cli.hub", "publish, discover and verify artifacts"),
        "cloud": Component("astro_mine.cli.cloud", "compile and submit cluster jobs"),
        "studio": Component("astro_mine.cli.studio", "the design studio"),
    }
)


class Kind(NamedTuple):
    """One scaffold kind: the module that writes it, and one line about what it emits."""

    module: str
    help: str


#: Authored-document kinds — ``astro-mine new <kind> <out>`` (RFC-0011 §7). The *verb* is
#: cross-component and lives here; the *template* belongs to whoever owns the format, which
#: is why each module delegates its final validation to that component's own loader.
DOCUMENT_KINDS: MappingProxyType[str, Kind] = MappingProxyType(
    {
        "asset": Kind("astro_mine.cli.scaffolds.asset", "a SADF asset (Fleet owns the format)"),
        "world": Kind("astro_mine.cli.scaffolds.world", "a WorldSpec (Worlds owns the format)"),
        "stack": Kind("astro_mine.cli.scaffolds.stack", "an autonomy stack spec (Mind's)"),
        "safety": Kind("astro_mine.cli.scaffolds.safety", "a SafetySpec (Guard's)"),
    }
)

#: Plugin kinds — ``astro-mine plugin new <kind>``. The name is the *extension group being
#: written against*, not the group the scaffold is declared in.
#:
#: The platform has eight extension groups; seven are here. The eighth is ``astro_mine.cli``
#: itself, and it had no scaffold for a structural reason that has now gone away: the
#: umbrella owned that group and could not depend on a component to template against it.
#: This package *is* that group's owner and depends on the platform, so a `cli` scaffold is
#: now possible — deliberately left out of this change rather than smuggled in (astro-mine-cli#12).
PLUGIN_KINDS: MappingProxyType[str, Kind] = MappingProxyType(
    {
        "tier": Kind("astro_mine.cli.scaffolds.tier", "an autonomy tier (astro_mine.mind.tier_plugins)"),
        "provider": Kind("astro_mine.cli.scaffolds.provider", "a content provider (astro_mine.providers)"),
        "field-model": Kind(
            "astro_mine.cli.scaffolds.field_model",
            "an illumination backend (astro_mine.field_models)",
        ),
        "runner": Kind("astro_mine.cli.scaffolds.runner", "a Bench backend (astro_mine.bench.runners)"),
        "solver": Kind(
            "astro_mine.cli.scaffolds.solver", "an allocation backend (astro_mine.allocate.solvers)"
        ),
        "algorithm": Kind(
            "astro_mine.cli.scaffolds.algorithm", "a MARL algorithm (astro_mine.learn.algorithms)"
        ),
        "curriculum": Kind(
            "astro_mine.cli.scaffolds.curriculum", "a curriculum (astro_mine.learn.curricula)"
        ),
    }
)

#: The four components that own an authored format and can therefore answer
#: "is this document mine?" for `astro-mine validate` (RFC-0011 §6). Each module exposes a
#: ``validator``; the router asks them in this order and refuses to guess when none claims.
VALIDATOR_OWNERS: tuple[str, ...] = ("core", "guard", "mind", "worlds")
