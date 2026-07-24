"""The static first-party verb manifest — plain strings, no imports, no dependencies.

Discovery alone (:mod:`astro_mine.cli._discovery`) cannot say anything about a component that is
**not installed**: with no ``astro-mine-learn`` there is no ``train`` entry point, and the best a
purely dynamic umbrella could manage is *"unknown command"* — which tells a user nothing about a
platform they are still learning the shape of. This table is the minimal fix (RFC-0011 §1b): it
maps the platform's own verbs to the distribution that provides each, so a missing component
produces *"`astro-mine train` needs astro-mine-learn — pip install astro-mine-learn"*.

It does two jobs, and both are why it stays strings:

1. **The install hint**, above.
2. **Top-level help text.** Listing a one-line description next to each verb would otherwise mean
   loading every provider to read its ``help`` — exactly the import-everything cost RFC-0011 §1a
   forbids. Taking first-party help from this table keeps ``astro-mine --help`` free. A verb's
   *complete* help still comes from the provider, on ``astro-mine <verb> --help``, where paying
   for one import is what the user asked for.

**It governs first-party verbs only.** A third-party verb is discovered dynamically, listed with
its providing distribution, and needs no entry here — the no-PR-to-extend rule (RFC-0011 §3) is
not quietly reintroduced through this file.

Entries are added when a component actually registers the verb, or ahead of it as a promise the
umbrella can keep honestly ("not installed"), never as a claim that it works.

``validate`` is deliberately **absent**: the umbrella owns that verb itself (RFC-0011 §6), so it
can never be the missing-component case this table exists to describe. Its own error names the
package that owns the format at hand — which is more specific than anything a static row could
say, since `validate` has several owners.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import NamedTuple

__all__ = ["FIRST_PARTY_VERBS", "FirstPartyVerb", "install_hint"]


class FirstPartyVerb(NamedTuple):
    """The distribution that provides a platform verb, and one line about what it does."""

    distribution: str
    help: str


#: Platform verb → provider. Ordered as a user meets them: get content, run it, score it, train,
#: publish, then the component-scoped surfaces. `astro-mine <component> <verb>` is RFC-0011 §2's
#: form for actions that are inherently component-scoped, so those components appear here as
#: single verbs (`studio`, `fleet`, …) rather than exploding their whole subcommand tree.
FIRST_PARTY_VERBS: MappingProxyType[str, FirstPartyVerb] = MappingProxyType(
    {
        "fetch": FirstPartyVerb("astro-mine-bench", "download a scenario's pinned content"),
        "list": FirstPartyVerb("astro-mine-bench", "list the scenarios in the zoo"),
        "score": FirstPartyVerb("astro-mine-bench", "run a policy on a scenario and score it"),
        "submit": FirstPartyVerb("astro-mine-bench", "submit a policy to a leaderboard"),
        "run": FirstPartyVerb("astro-mine-sim", "run a scenario in the simulator"),
        "record": FirstPartyVerb("astro-mine-sim", "record a self-contained Sim scenario file"),
        "train": FirstPartyVerb("astro-mine-learn", "train a policy and export it"),
        "publish": FirstPartyVerb("astro-mine-hub", "publish a signed artifact to a registry"),
        "search": FirstPartyVerb("astro-mine-hub", "discover artifacts in a registry"),
        "pull": FirstPartyVerb("astro-mine-hub", "pull and re-verify an artifact"),
        "verify": FirstPartyVerb("astro-mine-hub", "re-verify an artifact's supply chain"),
        "studio": FirstPartyVerb("astro-mine-studio", "the design studio (`studio serve`)"),
        "fleet": FirstPartyVerb("astro-mine-fleet", "author and publish SADF assets"),
        "worlds": FirstPartyVerb("astro-mine-worlds", "build and publish world bundles"),
        "prospect": FirstPartyVerb("astro-mine-prospect", "publish resource priors"),
        "link": FirstPartyVerb("astro-mine-link", "publish contact plans"),
        "mind": FirstPartyVerb("astro-mine-mind", "validate and compose planner stacks"),
        "guard": FirstPartyVerb("astro-mine-guard", "author, compile and falsify SafetySpecs"),
        "cloud": FirstPartyVerb("astro-mine-cloud", "submit and manage cluster jobs"),
    }
)


def install_hint(verb: str) -> str | None:
    """The one-line fix for a known verb whose component is not installed.

    ``None`` for a verb this table does not know — that case is an unknown-command error listing
    what *is* available, not a fabricated install suggestion.
    """
    known = FIRST_PARTY_VERBS.get(verb)
    if known is None:
        return None
    return (
        f"`astro-mine {verb}` needs {known.distribution} — "
        f"install it with `pip install {known.distribution}` "
        f"(or `uv add {known.distribution}`), then re-run."
    )
