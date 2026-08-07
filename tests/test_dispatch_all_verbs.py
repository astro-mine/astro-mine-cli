"""Every verb is reachable through the real dispatcher, and every exit status propagates.

`test_parser_parity` proves the 50 parsers are *shaped* right. This proves they are *wired*
right: that `astro-mine <component> <verb>` actually routes through
:func:`astro_mine.cli.main` -- two-phase parse, module import, `command.run` -- and that what
a handler returns becomes the process exit status.

Both matter separately. A component could have a perfect parser and be missing from the
registry, or be registered under a name that does not match its module, and parity would not
notice.

Everything here runs **in-process**. Spawning `astro-mine` 63 times costs minutes, because
each start pays a full platform component import; in-process it is seconds and the assertions
are the same. The subprocess path -- the one that proves the console script and its packaging
metadata work -- is covered once, in `test_installed_provider.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astro_mine.cli import main
from astro_mine.cli._registry import COMPONENTS

FIXTURE = Path(__file__).parent / "fixtures" / "parser-snapshot.json"


def _verbs() -> list[tuple[str, str | None]]:
    """(component, verb) for all 50; verb is None for Learn, which has no subcommands."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out: list[tuple[str, str | None]] = []
    for component, spec in sorted(fixture.items()):
        out += [(component, v) for v in sorted(spec["verbs"])] or [(component, None)]
    return out


@pytest.mark.parametrize(("component", "verb"), _verbs(), ids=lambda p: p or "-")
def test_verb_help_is_reachable_through_the_dispatcher(
    component: str, verb: str | None, capsys: pytest.CaptureFixture[str]
) -> None:
    """`astro-mine <component> <verb> --help` renders that verb's own help and exits 0.

    argparse raises SystemExit(0) for `--help`; reaching it at all is the assertion, because
    it means the dispatcher resolved the component, imported its module, built the parser and
    handed the tail over.
    """
    argv = [component, *([verb] if verb else []), "--help"]
    with pytest.raises(SystemExit) as caught:
        main(argv)
    assert caught.value.code == 0, argv

    out = capsys.readouterr().out
    assert out.strip(), f"{argv} produced no help output"
    # The prog line must read as the new grammar, never as a binary this change removed.
    assert f"astro-mine {component}" in out, argv


@pytest.mark.parametrize("component", sorted(COMPONENTS))
def test_component_help_lists_its_verbs(component: str, capsys: pytest.CaptureFixture[str]) -> None:
    """`astro-mine <component> --help` reaches the component's own parser."""
    with pytest.raises(SystemExit) as caught:
        main([component, "--help"])
    assert caught.value.code == 0
    assert f"astro-mine {component}" in capsys.readouterr().out


def test_the_root_listing_names_every_component(capsys: pytest.CaptureFixture[str]) -> None:
    """`astro-mine` with no arguments is a map of the platform, and exits 0."""
    assert main([]) == 0
    out = capsys.readouterr().out
    for name in COMPONENTS:
        assert name in out, f"{name} missing from the root listing"
    for router in ("validate", "new", "plugin"):
        assert router in out


def test_an_unknown_name_is_a_usage_error_that_suggests_the_nearest_real_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A typo gets the closest match, not a bare "unknown"."""
    with pytest.raises(SystemExit) as caught:
        main(["flete"])
    assert caught.value.code == 2
    assert "fleet" in capsys.readouterr().err


def test_exit_status_from_a_handler_reaches_the_caller() -> None:
    """A non-zero handler result becomes the process exit status, not an exception.

    `core validate` on a file that does not exist is the cheapest real failure in the
    platform: no network, no registry, no heavy import beyond Core itself.
    """
    assert main(["core", "validate", "/nonexistent/does-not-exist.yaml"]) == 1
