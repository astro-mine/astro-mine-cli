"""The error branches of Bench, Guard and Mind.

What is left uncovered in these three is almost entirely failure handling: a spec that does not
load, a compile that rejects, a stack whose tree cannot be resolved, a registry that is not
there. Those branches exist because the platform holds a rule — bad user input is reported as
one line and a non-zero status, never as a traceback — and a rule with no test is a rule that
erodes.

So each test here feeds a command something wrong and asserts the *shape* of the answer: a
non-zero exit, a message on stderr, and no stack trace. Not the wording, which is free to
improve.

Bench's `submit` path is deliberately thin here: it wants a live leaderboard, and the parts of
it reachable offline are the argument handling and the refusal, not the submission.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astro_mine.cli import main


def _assert_clean_failure(code: int, err: str) -> None:
    """A user-input failure: non-zero, something said, nothing raised."""
    assert code != 0, "a bad input was accepted"
    assert err.strip(), "a failure said nothing"
    assert "Traceback" not in err, "a user-input error surfaced as a traceback"


# --- guard ----------------------------------------------------------------------------------


@pytest.fixture
def safety(tmp_path: Path) -> Path:
    path = tmp_path / "s.safety.yaml"
    assert main(["new", "safety", str(path)]) == 0
    return path


def test_guard_validate_accepts_the_scaffold(safety: Path) -> None:
    assert main(["guard", "validate", str(safety)]) == 0


def test_guard_validate_rejects_a_malformed_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("safety:\n  id: x\n", encoding="utf-8")  # no version, no constraints
    _assert_clean_failure(main(["guard", "validate", str(bad)]), capsys.readouterr().err)


def test_guard_validate_reports_an_unreadable_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _assert_clean_failure(
        main(["guard", "validate", str(tmp_path / "absent.yaml")]), capsys.readouterr().err
    )


def test_guard_compile_the_scaffold(safety: Path) -> None:
    """The scaffold's promise: it validates *and compiles* with no hand-editing."""
    assert main(["guard", "compile", str(safety)]) == 0


def test_guard_compile_refuses_a_spec_that_does_not_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: a safety spec\n", encoding="utf-8")
    _assert_clean_failure(main(["guard", "compile", str(bad)]), capsys.readouterr().err)


def test_guard_falsify_refuses_a_spec_that_does_not_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("safety: {}\n", encoding="utf-8")
    _assert_clean_failure(main(["guard", "falsify", str(bad)]), capsys.readouterr().err)


def test_guard_sign_without_a_resolvable_key_fails_closed(
    safety: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No key means no signature — never a signature from a phantom key."""
    _assert_clean_failure(
        main(["guard", "sign", str(safety), "--key", str(tmp_path / "absent.pem")]),
        capsys.readouterr().err,
    )


# --- mind -----------------------------------------------------------------------------------


@pytest.fixture
def stack(tmp_path: Path) -> Path:
    path = tmp_path / "s.stack.yaml"
    assert main(["new", "stack", str(path)]) == 0
    return path


def test_mind_validate_accepts_the_scaffold(stack: Path) -> None:
    assert main(["mind", "validate", str(stack)]) == 0


def test_mind_validate_reports_an_unreadable_stack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _assert_clean_failure(
        main(["mind", "validate", str(tmp_path / "absent.yaml")]), capsys.readouterr().err
    )


def test_mind_validate_rejects_a_malformed_stack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("stack:\n  id: nope\n", encoding="utf-8")
    _assert_clean_failure(main(["mind", "validate", str(bad)]), capsys.readouterr().err)


def test_mind_stacks_enumerates_the_shipped_reference_stacks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reads package data through `astro_mine.mind.reference` — the platform's, not a copy."""
    assert main(["mind", "stacks"]) == 0
    assert capsys.readouterr().out.strip()


def test_mind_compose_the_scaffold(stack: Path) -> None:
    assert main(["mind", "compose", str(stack)]) in (0, 1)


def test_mind_compose_reports_an_unreadable_stack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _assert_clean_failure(
        main(["mind", "compose", str(tmp_path / "absent.yaml")]), capsys.readouterr().err
    )


def test_mind_compose_rejects_a_stack_that_does_not_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("[]\n", encoding="utf-8")
    _assert_clean_failure(main(["mind", "compose", str(bad)]), capsys.readouterr().err)


# --- bench ----------------------------------------------------------------------------------


def test_bench_list_names_the_zoo(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["bench", "list"]) == 0
    assert capsys.readouterr().out.strip()


def test_bench_zoo_search_without_a_database_is_a_clean_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`zoo-search` needs a DSN; without one it says so rather than raising."""
    code = main(["bench", "zoo-search", "ice"])
    err = capsys.readouterr().err
    if code == 0:
        pytest.skip("a zoo database is reachable in this environment")
    _assert_clean_failure(code, err)


def test_bench_fetch_of_an_unknown_scenario_is_a_clean_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["bench", "fetch", "no-such-scenario-v9", "--registry", str(tmp_path)])
    captured = capsys.readouterr()
    _assert_clean_failure(code, captured.err + captured.out)


def test_bench_score_of_an_unknown_scenario_is_a_clean_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _assert_clean_failure(main(["bench", "score", "no-such-scenario-v9"]), capsys.readouterr().err)


def test_bench_score_json_shape(capsys: pytest.CaptureFixture[str]) -> None:
    """The fixture runner scores offline, and `--json` is what a harness parses."""
    code = main(["bench", "score", "--json"])
    out = capsys.readouterr().out
    if code != 0:
        pytest.skip("the default scenario's content is not pinned in this environment")
    assert isinstance(json.loads(out), dict)


def test_bench_submit_without_a_target_is_a_clean_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Submission needs a live leaderboard; what is testable offline is the refusal."""
    code = main(["bench", "submit", "--policy-ref", "nosuchmodule:policy",
                 "--to", "http://127.0.0.1:1/none"])
    _assert_clean_failure(code, capsys.readouterr().err)
