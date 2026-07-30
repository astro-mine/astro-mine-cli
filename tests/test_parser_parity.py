"""Every verb's arguments are byte-identical to the ones the platform binaries had.

This is the acceptance criterion of astro-mine-cli#12 turned into a test. The change moved
~4,200 lines of parser and handler code out of `astro-mine-platform` and into this package;
the promise made to justify that was that *nothing about a command changes except its
address* -- `astro-mine-bench score …` becomes `astro-mine bench score …`, and every flag,
default, `nargs`, `choices`, `required` and help string survives.

`tests/fixtures/parser-snapshot.json` is the contract: 50 verbs, 189 arguments, captured from
the platform's own parsers at commit fd91454 -- *before* a line was deleted -- by
`scripts/snapshot_parsers.py`. A human cannot diff 189 arguments reliably, and reviewing 50
ports by eye is exactly how a `--trusted-key` or a `--no-verify` goes missing. So the machine
does it.

**What is deliberately NOT compared.** `prog` (`astro-mine-bench score` legitimately becomes
`astro-mine bench score`) and each component's *top-level* description (several were
`__doc__.splitlines()[0]` of a module whose docstring this change rewrites). Everything a user
types, and every string that tells them what to type, is compared exactly.

**Two normalizations, applied to both sides.**

1. *Binaries.* 109 help strings named a binary this change deletes -- *"Mint one with
   `astro-mine-hub keygen`"*. Leaving them would ship instructions to run a command that no
   longer exists, so they were re-addressed to `astro-mine hub keygen`. :func:`_readdress`
   applies that same rewrite to the fixture before comparing, so an expected re-addressing
   passes and a *substantive* help-text edit still fails. It rewrites only the
   `astro-mine-<component>` form; the distribution names `astro-mine-platform` and
   `astro-mine-cli` are untouched, as are GitHub URLs.

2. *Extras.* Normalization 1 was applied too widely once: `astro-mine-sim[bench]` is a
   **distribution plus extra**, not a binary, so re-addressing it produced `astro-mine
   sim[bench]` -- a shell command offered as a `pip install` target, which resolves to nothing
   (astro-mine-cli#19). Consolidation folded the per-component extras into the platform's
   `<component>-<extra>` namespace, so the honest target is `astro-mine-platform[sim-bench]`.
   :func:`_readdress` maps the fixture's `astro-mine-<component>[<extra>]` onto that form, and
   runs **before** the binary rewrite so the latter never sees an extra again.

Regenerating the fixture to make this pass is not a fix -- the fixture is the old behaviour,
and the old behaviour is the requirement. If a verb genuinely must change, that is a separate
change with its own justification, and the fixture moves in *that* commit.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from astro_mine.cli._registry import COMPONENTS

FIXTURE = Path(__file__).parent / "fixtures" / "parser-snapshot.json"

#: `astro-mine-sim[bench]` -> `astro-mine-platform[sim-bench]`. A retired distribution *with an
#: extra* is not a binary, and must not be rewritten as one: consolidation moved the extras into
#: the platform under `<component>-<extra>`, which is the only form that installs.
_OLD_EXTRA = re.compile(
    r"(?<![/\w-])astro-mine-(" + "|".join(sorted(COMPONENTS)) + r")\[([a-z0-9-]+)\]"
)

#: `astro-mine-hub keygen` -> `astro-mine hub keygen`, and nothing else. Not preceded by `/`
#: so GitHub URLs survive; the alternation lists components, so `astro-mine-platform` and
#: `astro-mine-cli` -- which are distributions, not commands -- survive too.
_OLD_BINARY = re.compile(
    r"(?<![/\w-])astro-mine-(" + "|".join(sorted(COMPONENTS)) + r")(?![\w-])"
)


def _readdress(value: Any) -> Any:
    """Rewrite the fixture's retired names to the ones this distribution actually offers.

    Extras first: once `astro-mine-sim[bench]` has become `astro-mine-platform[sim-bench]`,
    the binary pattern can no longer match it, so the order is what keeps the two rules from
    fighting over the same string.
    """
    if not isinstance(value, str):
        return value
    return _OLD_BINARY.sub(r"astro-mine \1", _OLD_EXTRA.sub(r"astro-mine-platform[\1-\2]", value))


@pytest.fixture(scope="session")
def snapshot() -> dict[str, Any]:
    return json.loads(_readdress(FIXTURE.read_text(encoding="utf-8")))


def _describe_action(action: argparse.Action) -> dict[str, Any]:
    """Identical to scripts/snapshot_parsers.py -- the two must not drift."""
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


def _built(component: str) -> dict[str, Any]:
    module = importlib.import_module(COMPONENTS[component].module)
    parser = argparse.ArgumentParser(prog=f"astro-mine {component}")
    module.command.add_arguments(parser)
    return _describe(parser)


@pytest.mark.parametrize("component", sorted(COMPONENTS))
def test_component_exposes_the_same_verbs(component: str, snapshot: dict[str, Any]) -> None:
    """No verb was dropped in the move, and none was invented."""
    assert sorted(_built(component)["verbs"]) == sorted(snapshot[component]["verbs"]), component


@pytest.mark.parametrize("component", sorted(COMPONENTS))
def test_component_level_arguments_match(component: str, snapshot: dict[str, Any]) -> None:
    """Flags that hang off the component itself, e.g. `astro-mine core --json validate …`."""
    assert _built(component)["actions"] == snapshot[component]["actions"], component


def _verb_ids() -> list[tuple[str, str]]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [(c, v) for c in sorted(COMPONENTS) for v in sorted(fixture[c]["verbs"])]


@pytest.mark.parametrize(("component", "verb"), _verb_ids(), ids=lambda p: p)
def test_every_verb_argument_matches(component: str, verb: str, snapshot: dict[str, Any]) -> None:
    """The 50-verb contract, one test per verb.

    Parameterized per verb rather than looped inside one test so a failure names the command
    that broke -- `test_every_verb_argument_matches[hub-publish]` -- instead of stopping at the
    first mismatch and hiding the rest.
    """
    built = _built(component)["verbs"][verb]
    expected = snapshot[component]["verbs"][verb]
    assert built["actions"] == expected["actions"], f"{component} {verb}"
    assert built["description"] == expected["description"], f"{component} {verb} description"


def test_the_fixture_covers_every_component_and_all_fifty_verbs(snapshot: dict[str, Any]) -> None:
    """Guards the guard: a fixture that silently lost entries would make this suite vacuous."""
    assert sorted(snapshot) == sorted(COMPONENTS)
    total = sum(len(c["verbs"]) or 1 for c in snapshot.values())
    assert total == 50, f"expected 50 verbs in the contract, found {total}"
