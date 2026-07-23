"""The shell's behaviour with nothing registered — the standup release's whole surface.

The interesting case here is the empty one. A dispatcher that has discovered no verbs is the
state every user hits before installing a component, and RFC-0011 §4 is explicit that the
umbrella degrades *honestly*: it says what is missing and what to do, and it never tracebacks.
The full degradation contract (naming the `pip install` for a known first-party verb) arrives
with discovery in #2; what is testable today is that the empty state is a clean, informative
exit rather than a crash or a lie.
"""

from __future__ import annotations

import pytest

from astro_mine.cli import build_parser, main


def test_bare_invocation_prints_help_and_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    """Asking a dispatcher what it can do is a legitimate question with a complete answer."""
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "usage: astro-mine" in out
    assert "No verbs are registered" in out


def test_empty_state_points_at_the_component_clis(capsys: pytest.CaptureFixture[str]) -> None:
    """The empty state must not read as "the platform has no commands".

    Every component CLI works today when invoked directly; only the umbrella's routing is
    pending. Saying so is the difference between an honest degraded surface and a dead end.
    """
    main([])
    out = capsys.readouterr().out
    assert "astro-mine-bench score" in out
    assert "issues/2" in out


def test_unknown_verb_fails(capsys: pytest.CaptureFixture[str]) -> None:
    """Silence on an unrecognized verb would be the dishonest case — argparse exits 2."""
    with pytest.raises(SystemExit) as excinfo:
        main(["definitely-not-a-verb"])
    assert excinfo.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0


def test_version_flag_reports_the_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.startswith("astro-mine ")


def test_parser_is_built_per_call() -> None:
    """Not a style point: #2's verb set is read from installed metadata at build time, so a
    cached module-level parser would freeze the environment as it was at first import."""
    assert build_parser() is not build_parser()
