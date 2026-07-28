"""The guards every plugin scaffold puts in front of a name.

Each of the eight kinds validates what the user asked to call things before writing a package,
and the checks are the same four everywhere: don't shadow a built-in, the plugin name must be a
registry-safe slug, the module name must be an importable Python identifier, and an existing
directory is not overwritten without `--force`.

They are worth testing together because they are the same contract eight times over. A scaffold
that skipped one would emit a package that installs and then fails at registration — the worst
place to find out, because the user has already built on it.

Parameterized by kind and by that kind's own name flag, which differ: `--runner`, `--backend`,
`--tier`, `--tag`, `--name-it`, `--verb`, `--kind`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astro_mine.cli import main

#: kind -> the flag that names the thing being scaffolded.
NAME_FLAG = {
    "tier": "--tier",
    "provider": "--kind",
    "field-model": "--backend",
    "runner": "--runner",
    "solver": "--backend",
    "algorithm": "--tag",
    "curriculum": "--name-it",
    "cli": "--verb",
}

#: The built-in names each kind refuses, because shadowing one produces a package that installs
#: and then loses to — or collides with — what the platform already provides.
SHADOWS = {"runner": "fixture", "field-model": "horizon"}

#: The three ways a kind handles its name, established by probing rather than assumed:
#:
#: CLOSED_SET   argparse `choices=` refuses an unusable value before any handler runs. The
#:              strongest of the three, and free.
#: VALIDATED    the name is free-form, and the scaffold checks it is a registry-safe slug.
#: UNCHECKED    the name is free-form and nothing checks it. See the KNOWN GAP test below.
CLOSED_SET = ["tier", "provider"]
VALIDATED = ["runner", "cli"]
UNCHECKED = ["field-model", "solver", "algorithm", "curriculum"]


@pytest.mark.parametrize("kind", sorted(NAME_FLAG))
def test_every_kind_writes_a_package(kind: str, tmp_path: Path) -> None:
    out = tmp_path / f"pkg-{kind}"
    assert main(["plugin", "new", kind, str(out)]) == 0
    assert (out / "pyproject.toml").exists()


@pytest.mark.parametrize("kind", sorted(NAME_FLAG))
def test_an_existing_directory_is_not_overwritten_without_force(kind: str, tmp_path: Path) -> None:
    """The scaffold refuses rather than clobbering work in progress."""
    out = tmp_path / "pkg"
    assert main(["plugin", "new", kind, str(out)]) == 0
    assert main(["plugin", "new", kind, str(out)]) != 0
    assert main(["plugin", "new", kind, str(out), "--force"]) == 0


@pytest.mark.parametrize("kind", VALIDATED)
def test_a_free_form_name_that_is_not_a_registry_slug_is_refused(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Entry-point names are matched literally, so `My Runner!` could never be looked up."""
    code = main(["plugin", "new", kind, str(tmp_path / "p"), NAME_FLAG[kind], "Not A Slug!"])
    assert code == 2, f"{kind} accepted an unusable name"
    assert capsys.readouterr().err.strip()


@pytest.mark.parametrize("kind", CLOSED_SET)
def test_a_constrained_name_is_rejected_by_the_parser(kind: str, tmp_path: Path) -> None:
    """`tier` and `provider` close their name flag with `choices=`.

    That is the better design and worth pinning: a closed set cannot drift into a scaffold
    that emits a plugin nothing will ever resolve.
    """
    with pytest.raises(SystemExit) as caught:
        main(["plugin", "new", kind, str(tmp_path / "p"), NAME_FLAG[kind], "Not A Slug!"])
    assert caught.value.code == 2


def test_the_cli_scaffold_refuses_a_verb_the_platform_owns(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`plugin new cli --verb validate` is refused: the CLI owns that router.

    `validate` is a router this CLI owns, so a third party claiming it is rejected at dispatch
    (`_dispatch.main` reports the collision and exits 2). The *scaffold* does not check, so the
    author finds out only after publishing — the one point at which the name is already in
    somebody's lockfile.

    Caught at authoring time since astro-mine-cli#14, which is the only moment the fix is
    cheap: after publication the name is in somebody's lockfile.
    """
    assert main(["plugin", "new", "cli", str(tmp_path / "p"), "--verb", "validate"]) == 2
    assert "already provides" in capsys.readouterr().err
    # A component name is reserved for the same reason.
    assert main(["plugin", "new", "cli", str(tmp_path / "q"), "--verb", "fleet"]) == 2


@pytest.mark.parametrize("kind", sorted(NAME_FLAG))
def test_a_module_name_that_is_not_an_identifier_is_refused(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The emitted package has to be importable; `--module 9lives` never could be."""
    code = main(["plugin", "new", kind, str(tmp_path / "p"), "--module", "9lives"])
    assert code == 2, f"{kind} accepted an unimportable module name"
    assert capsys.readouterr().err.strip()


@pytest.mark.parametrize("kind", sorted(NAME_FLAG))
def test_a_module_name_that_is_a_keyword_is_refused(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`import class` is a syntax error, so the scaffold must not offer to write it."""
    code = main(["plugin", "new", kind, str(tmp_path / "p"), "--module", "class"])
    assert code == 2, f"{kind} accepted a Python keyword as a module name"
    assert capsys.readouterr().err.strip()


@pytest.mark.parametrize("kind", sorted(SHADOWS))
def test_shadowing_a_built_in_name_is_refused(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A plugin may not claim a name the platform already provides.

    The scaffold catches it at authoring time, which is the only moment the fix is cheap: after
    publication the name is in someone's lockfile.
    """
    code = main(["plugin", "new", kind, str(tmp_path / "p"), NAME_FLAG[kind], SHADOWS[kind]])
    assert code == 2, f"{kind} let a plugin shadow {SHADOWS[kind]!r}"
    assert SHADOWS[kind] in capsys.readouterr().err


@pytest.mark.parametrize("kind", sorted(NAME_FLAG))
def test_a_custom_distribution_and_module_reach_the_emitted_pyproject(
    kind: str, tmp_path: Path
) -> None:
    """`--distribution` and `--module` are what the user will `pip install` and `import`."""
    out = tmp_path / "pkg"
    assert main(["plugin", "new", kind, str(out),
                 "--distribution", "my-thing", "--module", "my_thing"]) == 0
    pyproject = (out / "pyproject.toml").read_text(encoding="utf-8")
    assert "my-thing" in pyproject
    assert "my_thing" in pyproject


# --- document scaffolds ---------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["asset", "world", "stack", "safety"])
def test_document_scaffolds_refuse_to_clobber(kind: str, tmp_path: Path) -> None:
    out = tmp_path / f"{kind}.yaml"
    assert main(["new", kind, str(out)]) == 0
    assert main(["new", kind, str(out)]) != 0
    assert main(["new", kind, str(out), "--force"]) == 0


@pytest.mark.parametrize("kind", UNCHECKED)
def test_the_formerly_unchecked_kinds_now_refuse_an_unusable_name(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """These four used to write whatever name they were handed (astro-mine-cli#14).

    They emitted a package whose `[project.entry-points]` name could never be resolved --
    names are matched literally -- so the author found out at registration, after publishing.
    They now share the one rule in `scaffolds/_names.py` with `runner` and `cli`.
    """
    code = main(["plugin", "new", kind, str(tmp_path / "p"), NAME_FLAG[kind], "Not A Slug!"])
    assert code == 2, f"{kind} still accepts an unusable name"
    assert "entry-point name" in capsys.readouterr().err


@pytest.mark.parametrize("kind", sorted(NAME_FLAG))
def test_every_kind_accepts_its_own_default_name(kind: str, tmp_path: Path) -> None:
    """The rule must not refuse the scaffolds' own defaults.

    It did at first: the platform's ids are dotted (`marl.demo.algorithm`,
    `mind.control.mpc`), and a rule without `.` rejected them. Pinned so a future tightening
    cannot quietly break the happy path.
    """
    assert main(["plugin", "new", kind, str(tmp_path / f"p-{kind}")]) == 0
