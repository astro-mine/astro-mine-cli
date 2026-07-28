"""``astro-mine-guard`` CLI + the packaged anchor spec (G2.6/G2.7, astro-mine-guard#29).

Two things are proven here:

* the reviewed anchor ``SafetySpec`` resolves **from package data**, via ``importlib.resources`` and
  never a path relative to the repo root — the #55 / astro-mine-bench#37 wheel trap, and the reason
  ``astro-mine-mind`` had to inline a second copy of a *safety* contract;
* the four verbs (``validate``/``compile``/``falsify``/``sign``) work, and fail **closed** — an
  invalid or unsigned-key path is a failure, never a pass.
"""

from __future__ import annotations

# Migrated from astro-mine-platform, where these drove `astro-mine-guard <verb>` directly.
# The commands did not change -- only their address -- so the bodies are untouched and this
# shim re-points `main([...])` at the one executable: `astro-mine guard <verb>`.
from astro_mine.cli import main as _astro_mine


def main(argv=None):  # type: ignore[no-untyped-def]
    return _astro_mine(["guard", *(argv or [])])


import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- the packaged spec






# --------------------------------------------------------------------------- validate


def test_validate_anchor_ok() -> None:
    assert main(["validate", "anchor"]) == 0


def test_validate_reports_actionable_error_and_fails_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.safety.yaml"
    bad.write_text('safety_version: "0.1"\nsafety:\n  id: x\n', encoding="utf-8")
    assert main(["validate", str(bad)]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    # names the missing fields (the JSON-Schema layer), not a bare traceback
    assert "required property" in err


def test_validate_defaults_to_the_anchor() -> None:
    assert main(["validate"]) == 0  # no path → the shipped anchor


# --------------------------------------------------------------------------- compile


def test_compile_emits_artifact_and_hash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "anchor.compiled.json"
    assert main(["compile", "anchor", "--out", str(out)]) == 0
    model = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(model, dict)
    err = capsys.readouterr().err
    assert "compiled_hash: sha256:" in err
    assert "spec_hash: sha256:".replace(" ", "") in err.replace(" ", "")


def test_compile_is_deterministic(tmp_path: Path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    main(["compile", "anchor", "--out", str(a)])
    main(["compile", "anchor", "--out", str(b)])
    assert a.read_bytes() == b.read_bytes()  # content-addressed ⇒ byte-identical


# --------------------------------------------------------------------------- sign


def test_sign_validates_first_and_verifies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from astro_mine.guard.spec import generate_keypair

    priv, pub = generate_keypair()
    key = tmp_path / "k.key.pem"
    pubkey = tmp_path / "k.pub.pem"
    key.write_bytes(priv)
    pubkey.write_bytes(pub)

    code = main(["sign", "anchor", "--key", str(key), "--pub", str(pubkey), "--verify"])
    assert code == 0
    out = capsys.readouterr().out
    assert "content_hash: sha256:" in out
    assert "verified:     True" in out


def test_sign_refuses_missing_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["sign", "anchor", "--key", str(tmp_path / "absent.pem")])
    assert code == 1
    assert "no signing key" in capsys.readouterr().err


def test_sign_refuses_invalid_spec(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from astro_mine.guard.spec import generate_keypair

    priv, _pub = generate_keypair()
    key = tmp_path / "k.key.pem"
    key.write_bytes(priv)
    bad = tmp_path / "bad.safety.yaml"
    bad.write_text('safety_version: "0.1"\nsafety:\n  id: x\n', encoding="utf-8")
    assert main(["sign", str(bad), "--key", str(key)]) == 1
    assert "refusing to sign an invalid spec" in capsys.readouterr().err


# --------------------------------------------------------------------------- falsify


def test_falsify_search_is_real_and_shield_holds(capsys: pytest.CaptureFixture[str]) -> None:
    pytest.importorskip(
        "astro_mine.guard._core", reason="Rust safety core not built (maturin develop / uv sync)"
    )
    assert main(["falsify", "--trials", "2", "--horizon", "40"]) == 0
    out = capsys.readouterr().out
    assert "the search is real" in out  # the unshielded control breached (non-vacuous)
    assert "shield held across 2 seed(s)" in out


def test_falsify_accepts_anchor_like_its_three_siblings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`falsify anchor` used to be `unrecognized arguments: anchor` (issue #35)."""
    pytest.importorskip("astro_mine.guard._core", reason="Rust safety core not built")
    assert main(["falsify", "anchor", "--trials", "1", "--horizon", "40"]) == 0
    assert "shield held across 1 seed(s)" in capsys.readouterr().out




def test_falsify_reports_a_bad_spec_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope.safety.yaml"
    assert main(["falsify", str(missing)]) == 1
    assert "cannot read" in capsys.readouterr().err

    bad = tmp_path / "bad.safety.yaml"
    bad.write_text('safety_version: "0.1"\nsafety:\n  id: x\n', encoding="utf-8")
    assert main(["falsify", str(bad)]) == 1
    err = capsys.readouterr().err
    assert "invalid spec" in err
    assert "Traceback" not in err


# --------------------------------------------------------------------------- the wheel boundary


