"""Nothing this CLI prints or writes may name a distribution or binary that no longer exists.

Consolidation retired seventeen `astro-mine-<component>` distributions and every
`astro-mine-<component>` binary. Two bugs came straight out of that (astro-mine-cli#18, #19), and
they are the same bug twice:

* `astro-mine plugin new solver` wrote `dependencies = ["astro-mine-allocate"]`, so the package it
  scaffolded **could not be installed** -- the one thing a scaffold exists to guarantee.
* `astro-mine studio serve` ended with `pip install astro-mine-studio[serve]`, and
  `astro-mine bench score --help` offered `astro-mine-sim[bench]` (re-addressed at one point to
  `astro-mine sim[bench]`, a shell command used as a pip target, which is worse).

Both were found by a human reading generated output months later. A name that resolves to nothing
is not a cosmetic defect: it sends the reader to pip, pip reports "no matching distribution", and
they conclude their environment is broken rather than the message. So the rule is asserted rather
than reviewed.

**What the tests check, and why in three pieces.** The generated files and the printed hints are
checked by *running* every scaffold, because that is the artifact a user actually holds. The help
strings are checked by walking the parsers, because a help string is reachable without running
anything and no scaffold test would ever see it. Between them they cover every string this package
puts in front of a user.

**Not a source-text scan.** Prose that *quotes* a retired name while explaining why it is retired is
correct and must stay -- `studio/__init__.py` documents the exact string it stopped printing. A
grep over the source would fail on the comment that prevents the regression.
"""

from __future__ import annotations

import argparse
import pkgutil
import re
import tomllib
from pathlib import Path

import pytest

import astro_mine
from astro_mine.cli import main
from astro_mine.cli._dispatch import _ROUTERS
from astro_mine.cli._registry import COMPONENTS, DOCUMENT_KINDS, PLUGIN_KINDS

#: The distributions consolidation retired, derived from the namespace rather than listed, so a
#: component added or renamed later cannot leave a stale allowlist behind. `cli` is excluded: it is
#: the one `astro_mine.<name>` subpackage whose `astro-mine-<name>` distribution is real.
RETIRED = sorted(
    f"astro-mine-{m.name}"
    for m in pkgutil.iter_modules(astro_mine.__path__)
    if m.ispkg and m.name != "cli"
)

#: The distributions that do exist. Anything else beginning `astro-mine-` in generated metadata is
#: a name a user cannot install.
LIVE_DISTRIBUTIONS = frozenset({"astro-mine-platform", "astro-mine-cli"})

#: `astro-mine-worlds`, `astro-mine-sim[bench]`, `astro-mine-hub keygen` -- a retired distribution
#: or the binary it used to install. Not preceded by `/`, so GitHub URLs survive; `astro-mine-api`
#: survives too, because Studio's message names it deliberately as the distribution that *will*
#: own the REST surface, and naming an unbuilt thing as unbuilt is the honest form.
_RETIRED_RE = re.compile(
    r"(?<![/\w-])(" + "|".join(re.escape(name) for name in RETIRED) + r")(?![\w-])"
)


def _offences(text: str) -> list[str]:
    return sorted(set(_RETIRED_RE.findall(text)))


def _requirement_names(pyproject: Path) -> list[str]:
    """The distribution names in a generated `[project].dependencies`, stripped of everything else.

    A hand-rolled split rather than `packaging.requirements`: this package depends only on the
    platform (`test_packaging.py`), and a scaffold's dependency list is simple enough that the
    parser is three characters of `re`.
    """
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return [
        re.split(r"[\[<>=!~;\s]", requirement, maxsplit=1)[0]
        for requirement in data["project"].get("dependencies", [])
    ]


# --- what the scaffolds write ------------------------------------------------------------------

#: Every plugin kind, including the `cli` kind this package owns outright (it is deliberately
#: absent from `PLUGIN_KINDS`, so parameterizing on that table alone would skip it).
ALL_PLUGIN_KINDS = sorted({*PLUGIN_KINDS, "cli"})


@pytest.mark.parametrize("kind", ALL_PLUGIN_KINDS)
def test_a_scaffolded_package_declares_a_dependency_that_exists(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`pip install -e <scaffold>` must be able to succeed — astro-mine-cli#18.

    Each kind used to name its owning component's distribution (`astro-mine-allocate`,
    `astro-mine-learn`, and for `tier` a pair of them). None of those resolve, so the emitted
    package was uninstallable from the moment it was written.
    """
    out = tmp_path / f"pkg-{kind}"
    assert main(["plugin", "new", kind, str(out)]) == 0
    capsys.readouterr()

    names = _requirement_names(out / "pyproject.toml")
    astro = [name for name in names if name.startswith("astro-mine")]
    dead = sorted(set(astro) - LIVE_DISTRIBUTIONS)
    assert not dead, (
        f"`plugin new {kind}` scaffolds a package depending on {dead}, which pip cannot resolve"
    )


@pytest.mark.parametrize("kind", ALL_PLUGIN_KINDS)
def test_a_scaffolded_package_names_nothing_retired(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Neither the files nor the "now do this" hint printed after them."""
    out = tmp_path / f"pkg-{kind}"
    assert main(["plugin", "new", kind, str(out)]) == 0
    captured = capsys.readouterr()

    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        offences = _offences(path.read_text(encoding="utf-8"))
        assert not offences, f"`plugin new {kind}` wrote {offences} into {path.relative_to(out)}"
    hint = captured.out + captured.err
    assert not _offences(hint), f"`plugin new {kind}` printed {_offences(hint)}"


#: `astro-mine new world` writes bytes this repo does not own: Worlds' scaffold calls
#: `astro_mine.worlds.spec.example_world_spec_text`, exactly as the thin-wrapper rule requires
#: (`architecture/cli.md` §7 -- the template belongs to the format's owner, so the two cannot
#: drift). That is why `world` carried a strict xfail here: the shipped example pointed at
#: `astro-mine-worlds validate`, a binary consolidation deleted, and this repo could not fix it.
#:
#: astro-mine/astro-mine-platform#6 fixed it, the strict marker turned the pass into a failure,
#: and this is that block being deleted -- which is the whole reason it was strict. Every
#: document kind is now checked with no exemption.
_DOCUMENT_KINDS = sorted(DOCUMENT_KINDS)


@pytest.mark.parametrize("kind", _DOCUMENT_KINDS)
def test_a_scaffolded_document_names_nothing_retired(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The document scaffolds carry command hints in comments, and those are read and typed.

    Guard's SafetySpec template is the sharpest case: it lists four commands in a header comment,
    and every one of them named a binary that consolidation deleted.
    """
    out = tmp_path / f"{kind}.yaml"
    assert main(["new", kind, str(out)]) == 0
    captured = capsys.readouterr()

    written = out.read_text(encoding="utf-8")
    assert not _offences(written), f"`new {kind}` wrote {_offences(written)}"
    hint = captured.out + captured.err
    assert not _offences(hint), f"`new {kind}` printed {_offences(hint)}"


# --- what the parsers say ----------------------------------------------------------------------


def _help_strings(parser: argparse.ArgumentParser) -> list[str]:
    """Every user-visible string in a parser tree: descriptions, epilogs, and per-action help."""
    found = [parser.description or "", parser.epilog or ""]
    for action in parser._actions:
        found.append(action.help or "")
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                found.extend(_help_strings(sub))
    return found


@pytest.mark.parametrize("component", sorted(COMPONENTS))
def test_no_component_help_string_names_something_retired(component: str) -> None:
    """astro-mine-cli#19's sibling sweep, kept swept.

    `bench score --help` advertised `astro-mine-sim[bench]` as the extra that supplies the Sim
    runner. The distribution is gone and the extra moved into the platform's `<component>-<extra>`
    namespace, so the only form that installs is `astro-mine-platform[sim-bench]`.
    """
    import importlib

    module = importlib.import_module(COMPONENTS[component].module)
    parser = argparse.ArgumentParser(prog=f"astro-mine {component}")
    module.command.add_arguments(parser)

    for text in _help_strings(parser):
        assert not _offences(text), f"`astro-mine {component}` help names {_offences(text)}: {text}"


@pytest.mark.parametrize("router", sorted(_ROUTERS))
def test_no_router_help_string_names_something_retired(router: str) -> None:
    """`validate`, `new` and `plugin new` — the three verbs this package owns outright."""
    parser = argparse.ArgumentParser(prog=f"astro-mine {router}")
    _ROUTERS[router].add_arguments(parser)

    for text in _help_strings(parser):
        assert not _offences(text), f"`astro-mine {router}` help names {_offences(text)}: {text}"
