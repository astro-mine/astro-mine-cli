"""Dispatch: routing, exit status, and the degradation contract (RFC-0011 §4)."""

from __future__ import annotations

import pytest

from _verbs import make_entry_point
from astro_mine.cli import main


@pytest.fixture
def verbs() -> dict[str, object]:
    return {
        "echo": make_entry_point("echo", "ECHO"),
        "quiet": make_entry_point("quiet", "RETURNS_NONE"),
        "boom": make_entry_point("boom", "EXPLODING"),
        "bogus": make_entry_point("bogus", "MALFORMED"),
    }


def test_routes_to_the_verb_and_passes_its_arguments(capsys, verbs) -> None:  # type: ignore[no-untyped-def]
    assert main(["echo", "hello world"], verbs=verbs) == 0
    assert capsys.readouterr().out.strip() == "hello world"


def test_the_verbs_exit_status_becomes_the_process_status(verbs) -> None:  # type: ignore[no-untyped-def]
    """A wrapper that discards the exit code turns a failing command into a passing script."""
    assert main(["echo", "x", "--exit-code", "3"], verbs=verbs) == 3


def test_a_verb_returning_none_succeeds(verbs) -> None:  # type: ignore[no-untyped-def]
    """`sys.exit(None)` means success everywhere else in Python; a component that finished its
    work should not be punished with a crash for following the convention."""
    assert main(["quiet"], verbs=verbs) == 0


def test_a_failure_inside_a_verb_is_not_swallowed(verbs) -> None:  # type: ignore[no-untyped-def]
    """The umbrella catches *environment* problems, never a component's own errors — hiding
    those would make the umbrella the thing you have to remove to debug your tool."""
    with pytest.raises(RuntimeError, match="the component itself failed"):
        main(["boom"], verbs=verbs)


def test_a_verbs_own_help_comes_from_the_provider(capsys, verbs) -> None:  # type: ignore[no-untyped-def]
    """The top-level listing is static, but `astro-mine <verb> --help` is the real thing: at that
    point the user has asked for one verb, so paying for one import is exactly right."""
    with pytest.raises(SystemExit) as excinfo:
        main(["echo", "--help"], verbs=verbs)
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "astro-mine echo" in out
    assert "--exit-code" in out


def test_an_unknown_verb_lists_what_is_available(capsys, verbs) -> None:  # type: ignore[no-untyped-def]
    """Not in the manifest and not installed: this one really is a typo, and inventing an install
    suggestion would send the user to a package that does not exist."""
    with pytest.raises(SystemExit) as excinfo:
        main(["frobnicate"], verbs=verbs)
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "unknown component or verb 'frobnicate'" in err
    assert "echo" in err


def test_a_malformed_provider_is_reported_not_raised(capsys, verbs) -> None:  # type: ignore[no-untyped-def]
    """A packaging bug in someone else's distribution must not surface as a traceback through
    this package — the reader would file the issue against the wrong repo."""
    assert main(["bogus"], verbs=verbs) == 2
    err = capsys.readouterr().err
    assert "does not satisfy the astro_mine.cli contract" in err
    assert "_verbs:MALFORMED" in err
    assert "Traceback" not in err


def test_a_verb_collision_is_reported_not_raised(capsys, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Discovery raises; the CLI reports. Both are right for their layer.

    Patched at the metadata boundary rather than at our own function, so the whole real path runs:
    main → discover_verbs → entry_points → collision → a message the user can act on.
    """
    clashing = (make_entry_point("echo", "ECHO"), make_entry_point("echo", "RETURNS_NONE"))
    monkeypatch.setattr(
        "astro_mine.cli._discovery.entry_points", lambda group=None: clashing, raising=True
    )
    assert main(["echo"]) == 2
    err = capsys.readouterr().err
    assert "claimed by both" in err
    assert "Traceback" not in err


def test_top_level_help_lists_components_routers_and_third_party_verbs(capsys, verbs) -> None:  # type: ignore[no-untyped-def]
    """The listing is the map of the platform (UC-A3), and it names all three sources.

    It used to also list first-party verbs that were *not installed*, with the distribution to
    `pip install` for each. That section is gone because the state is gone: every component
    ships in the one distribution this package depends on, so nothing first-party can be
    absent. What remains is the honest set — 13 components, 3 routers, and whatever third
    parties have registered, each described from metadata rather than by importing it.
    """
    assert main([], verbs=verbs) == 0
    out = capsys.readouterr().out
    assert "echo" in out
    assert "provided by _verbs:ECHO" in out  # third-party: described from metadata
    assert "Components" in out and "Routers" in out
    assert "bench" in out and "fleet" in out
