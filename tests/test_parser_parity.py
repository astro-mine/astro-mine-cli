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

**Three normalizations, applied to both sides.**

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

3. *The resolved content store.* `bench fetch --registry` renders its default by resolving it
   against the running user's home, so the help string reads `/home/djankov/...` on one machine and
   `/home/runner/...` on CI -- a difference in *where the test ran*, not in what the command does.
   :func:`_despecialize` collapses the resolved path to a token on both sides. It is a
   normalization rather than a fixture edit because the command did not change: resolving the
   default is what makes the help useful, and the fixture recorded a resolution, not a decision.

Regenerating the fixture to make this pass is not a fix -- the fixture is the old behaviour,
and the old behaviour is the requirement. If a verb genuinely must change, that is a separate
change with its own justification, and the fixture moves in *that* commit.

**One verb has genuinely changed, and the fixture moved with it** (astro-mine-cli#35/#36). `fleet
new` defaulted its scaffolded `--id` to `example.<kind>`, and a SADF `identity.id` *is* the
artifact's registry name at publish -- so every asset this command scaffolded was born violating
`conventions.md` §13 and unable to publish. The default is now `example-<kind>` and the help string
says so. This is not a re-addressing, so it is not a :func:`_readdress` rule: it is a behaviour
change, the fixture records the new behaviour, and this paragraph is the justification the note
above asks for. It is the first substantive divergence from the platform's parsers since the move.

**Components added after the move are excluded, by name.** A fixture recording what the platform's
binaries declared cannot record a group that never was one, and back-filling it would turn the
contract into a mirror of the current code -- which is the failure mode this whole file exists to
prevent. :data:`POST_MOVE` names them, and
:func:`test_the_fixture_covers_every_component_and_all_fifty_verbs` asserts the exclusion is
exactly that set, so a *ported* component silently vanishing from the fixture still fails.
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

#: Component groups that did not exist as a platform binary, so the fixture cannot describe them.
#: `seal` is the first (astro-mine-cli#17): the platform's signing component shipped no CLI at all,
#: which is why the CLI reference had to list it under "commands that do not exist".
#:
#: Adding a name here is how a genuinely new group is admitted. It is NOT how a ported command
#: escapes the contract -- a verb that changes is a separate change with its own justification, and
#: the fixture moves in that commit.
POST_MOVE: frozenset[str] = frozenset({"seal"})

#: The components the fixture is a contract for: everything that was a binary before the move.
PORTED: tuple[str, ...] = tuple(sorted(set(COMPONENTS) - POST_MOVE))

#: `astro-mine-sim[bench]` -> `astro-mine-platform[sim-bench]`. A retired distribution *with an
#: extra* is not a binary, and must not be rewritten as one: consolidation moved the extras into
#: the platform under `<component>-<extra>`, which is the only form that installs.
_OLD_EXTRA = re.compile(
    r"(?<![/\w-])astro-mine-(" + "|".join(sorted(COMPONENTS)) + r")\[([a-z0-9-]+)\]"
)

#: `astro-mine-hub keygen` -> `astro-mine hub keygen`, and nothing else. Not preceded by `/`
#: so GitHub URLs survive; the alternation lists components, so `astro-mine-platform` and
#: `astro-mine-cli` -- which are distributions, not commands -- survive too.
_OLD_BINARY = re.compile(r"(?<![/\w-])astro-mine-(" + "|".join(sorted(COMPONENTS)) + r")(?![\w-])")

#: `bench fetch --registry` renders its default by *resolving* it -- `default_store_path()` is
#: `$XDG_CACHE_HOME`-or-`~/.cache` joined with `astro-mine/hub-registry` -- so the help string
#: names whichever home the process is running under. The fixture froze one machine's answer
#: (`/home/djankov/...`) and CI is another (`/home/runner/...`), which failed the contract for a
#: difference that is not a change in behaviour. Showing the caller their own resolved path is the
#: better help text, so the *comparison* is what gets normalized, not the command: both sides have
#: the resolved store collapsed to a token, and the rest of the string -- `$ASTRO_MINE_HUB_REGISTRY`
#: taking precedence, the trailing `astro-mine/hub-registry` segments -- is still compared exactly.
#: Anchored on the `astro-mine/hub-registry` tail, so the workspace's `files/hub-registry` keys
#: (whose defaults are constants, not machine-derived) are untouched.
_RESOLVED_STORE = re.compile(r"/[\w.-]+(?:/[\w.-]+)*/astro-mine/hub-registry(?![\w-])")

#: What :data:`_RESOLVED_STORE` collapses to. Not a valid path, deliberately: if this ever leaks
#: into a comparison it should look wrong rather than plausibly pass.
_STORE_TOKEN = "<resolved default store>"


def _despecialize(text: str) -> str:
    """Collapse the machine-dependent parts of a parser description. Applied to *both* sides."""
    return _RESOLVED_STORE.sub(_STORE_TOKEN, text)


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
    return json.loads(_despecialize(_readdress(FIXTURE.read_text(encoding="utf-8"))))


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
    return json.loads(_despecialize(json.dumps(_describe(parser))))


@pytest.mark.parametrize("component", PORTED)
def test_component_exposes_the_same_verbs(component: str, snapshot: dict[str, Any]) -> None:
    """No verb was dropped in the move, and none was invented."""
    assert sorted(_built(component)["verbs"]) == sorted(snapshot[component]["verbs"]), component


@pytest.mark.parametrize("component", PORTED)
def test_component_level_arguments_match(component: str, snapshot: dict[str, Any]) -> None:
    """Flags that hang off the component itself, e.g. `astro-mine core --json validate …`."""
    assert _built(component)["actions"] == snapshot[component]["actions"], component


def _verb_ids() -> list[tuple[str, str]]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [(c, v) for c in PORTED for v in sorted(fixture[c]["verbs"])]


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
    """Guards the guard: a fixture that silently lost entries would make this suite vacuous.

    The exclusion is asserted as an equality, not a subset: a ported component dropping out of the
    fixture and a new group being added are both "the fixture no longer covers everything", and
    only one of them is allowed. Naming the difference exactly is what tells them apart.
    """
    assert sorted(snapshot) == list(PORTED)
    assert set(COMPONENTS) - set(snapshot) == POST_MOVE, (
        "a component is missing from the fixture without being declared post-move"
    )
    total = sum(len(c["verbs"]) or 1 for c in snapshot.values())
    assert total == 50, f"expected 50 verbs in the contract, found {total}"


def test_the_store_normalization_collapses_only_the_resolved_default() -> None:
    """Guards normalization 3: too narrow and CI fails again, too wide and a real edit slips past.

    The negative half is the load-bearing one. `files/hub-registry` appears in the contract as
    Guard's dev-key defaults, and those are *constants* -- the same string on every machine -- so
    collapsing them would hide a genuine change to where `guard sign` looks for a key.
    """
    for home in ("/home/djankov", "/home/runner", "/Users/someone/Library/Caches"):
        rendered = f"populate (default: $X, else {home}/.cache/astro-mine/hub-registry)"
        assert _despecialize(rendered) == f"populate (default: $X, else {_STORE_TOKEN})"

    untouched = (
        "PosixPath('/mnt/d/MyProjects/AstroMine/files/hub-registry/keys/anchor-dev.key.pem')",
        "the cache dir `astro-mine bench fetch` writes to",
        "hub-registry",
    )
    for text in untouched:
        assert _despecialize(text) == text, text


def test_the_contract_carries_no_machine_dependent_path(snapshot: dict[str, Any]) -> None:
    """No *newly* frozen home directory. A path under a home is a machine's answer, not a contract.

    Checked on the normalized snapshot, so the one known resolution is already a token: this fails
    on the next help string that bakes in `Path.home()` without a normalization to go with it.
    """
    leaked = re.findall(r"/(?:home|Users|root)/[\w.-]+", json.dumps(snapshot))
    assert not leaked, f"machine-dependent paths in the contract: {sorted(set(leaked))}"
