"""The three routers: `new`, `plugin new`, and `validate`.

These are the only verbs this package owns outright, because all three *route* rather than do
— deciding which component owns a document or a kind is the one job no component can hold
without importing its siblings (`conventions.md §1.1`).

**What replaced the old suite.** The previous tests were built almost entirely around
degradation: a kind whose component is not installed, a component installed but offering no
scaffold, an environment with no validators at all. None of those states can occur now — the
platform is one distribution and every owner ships in it — so testing them would be asserting
behaviour that cannot happen. What is worth testing instead is that each of the 12 kinds
actually produces something, that what `new` writes is what `validate` accepts, and that
third-party extension still works with no PR here.

The scaffold→validate round trip is the sharpest test in this file. RFC-0011 §7's whole point
is that the *template* stays with the format's owner, so `astro-mine new asset` and Fleet's
schema cannot drift; asserting the output validates is what proves the delegation is real
rather than a copied template slowly going stale.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from _verbs import make_entry_point
from astro_mine.cli import main
from astro_mine.cli._registry import DOCUMENT_KINDS, PLUGIN_KINDS
from astro_mine.cli._scaffolds import (
    DOCUMENT_SCAFFOLD_GROUP,
    PLUGIN_SCAFFOLD_GROUP,
    ScaffoldCollisionError,
    discover_scaffolds,
)
from astro_mine.cli._validators import discover_validators


@pytest.mark.parametrize("kind", sorted(DOCUMENT_KINDS))
def test_new_writes_a_document_that_validate_accepts(kind: str, tmp_path: Path) -> None:
    """The round trip, per document kind — the proof that the owner writes its own bytes."""
    out = tmp_path / f"{kind}.yaml"
    assert main(["new", kind, str(out)]) == 0, f"`astro-mine new {kind}` failed"
    assert out.exists() and out.read_text(encoding="utf-8").strip()
    assert main(["validate", str(out)]) == 0, f"`astro-mine new {kind}` output did not validate"


@pytest.mark.parametrize("kind", sorted(PLUGIN_KINDS))
def test_plugin_new_writes_an_installable_package(kind: str, tmp_path: Path) -> None:
    """Every plugin kind emits a package with, at minimum, a pyproject declaring its group."""
    out = tmp_path / f"pkg-{kind}"
    assert main(["plugin", "new", kind, str(out)]) == 0, f"`plugin new {kind}` failed"
    pyproject = out / "pyproject.toml"
    assert pyproject.exists(), f"{kind} scaffold wrote no pyproject.toml"
    assert "entry-points" in pyproject.read_text(encoding="utf-8")


def test_the_cli_plugin_kind_is_the_eighth_and_is_built_in(tmp_path: Path) -> None:
    """`cli` is offered by this package itself, not by a component.

    It is the one extension group the platform has that no component owns — and before this
    change it could not have a scaffold at all, because the umbrella was forbidden from
    depending on anything it would template against.
    """
    assert "cli" not in PLUGIN_KINDS
    assert main(["plugin", "new", "cli", str(tmp_path / "verb")]) == 0


def test_every_first_party_kind_resolves_to_a_real_object() -> None:
    """The registry's module:attr pairs are checked, not trusted.

    A typo in `_registry` would otherwise surface only when a user typed that exact kind.
    """
    for group, table in (
        (DOCUMENT_SCAFFOLD_GROUP, DOCUMENT_KINDS),
        (PLUGIN_SCAFFOLD_GROUP, PLUGIN_KINDS),
    ):
        available = discover_scaffolds(group)
        for kind in table:
            scaffold = available[kind].load()
            assert scaffold.name and scaffold.help
            assert callable(scaffold.add_arguments) and callable(scaffold.run)


def test_a_third_party_kind_is_offered_alongside_the_platforms() -> None:
    """No PR to extend: an outside package registering into the group gains a kind."""
    entry = make_entry_point("mykind", "ECHO", DOCUMENT_SCAFFOLD_GROUP)
    available = discover_scaffolds(DOCUMENT_SCAFFOLD_GROUP, entries=[entry])
    assert "mykind" in available
    assert set(DOCUMENT_KINDS) <= set(available), "built-ins must survive third-party discovery"


def test_a_third_party_may_not_silently_take_over_a_platform_kind() -> None:
    """Which package wrote a user's starting file is provenance, so a clash is a hard error.

    A silent winner would mean `astro-mine new asset` writes different bytes on two machines
    with nothing to tell them apart — and the divergence gets baked into whatever is built on
    top of it.
    """
    entry = make_entry_point("asset", "ECHO", DOCUMENT_SCAFFOLD_GROUP)
    with pytest.raises(ScaffoldCollisionError) as caught:
        discover_scaffolds(DOCUMENT_SCAFFOLD_GROUP, entries=[entry])
    assert "asset" in str(caught.value)


def test_an_unknown_kind_suggests_the_nearest_real_one(capsys: pytest.CaptureFixture[str]) -> None:
    """With every component present, an unrecognized kind is a typo — so answer like one."""
    assert main(["new", "assset", "/tmp/x.yaml"]) == 2
    err = capsys.readouterr().err
    assert "asset" in err


def test_the_four_format_owners_are_always_available() -> None:
    """`validate` federates Core, Guard, Mind and Worlds without reading any metadata."""
    names = {v.name for v in discover_validators(entries=[])}
    assert {"core", "guard", "mind", "worlds"} <= names


def test_validate_refuses_to_guess_at_a_document_nobody_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A document is never checked against a guessed schema."""
    stray = tmp_path / "stray.yaml"
    stray.write_text("just: a mapping\n", encoding="utf-8")
    assert main(["validate", str(stray)]) == 1
    assert "no installed validator recognizes" in capsys.readouterr().err
