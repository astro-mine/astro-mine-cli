"""The claims that only a real installation can prove.

Everything else in this suite injects entry points, which is fast and precise but shares one
blind spot: it never exercises the packaging metadata that makes the whole mechanism work in the
first place. So this module does it the long way — build the wheel, create an empty virtualenv,
install the umbrella plus an unrelated third-party distribution, and drive the console script as
a user would.

Two claims live or die here:

* **No PR to extend** (RFC-0011 §3) — ``am-cli-test-provider`` is not an ``astro-mine-*`` package
  and this repo contains no reference to its verbs, yet ``astro-mine demo`` works.
* **Listing imports nothing** (RFC-0011 §1a) — asserted in a clean interpreter, where a stray
  import cannot be masked by another test having already imported the module.

Marked ``integration`` because it shells out and builds; it is not deselected in CI, where these
are the two properties most worth defending.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[1]
PROVIDER = REPO_ROOT / "tests" / "fixtures" / "provider"

# The negative assertion, run inside the venv: build the top-level help — the operation most
# tempting to implement by loading every provider — and prove the provider stayed unimported.
_NO_IMPORT_PROBE = """
import sys
from astro_mine.cli import main
try:
    main(["--help"])
except SystemExit:
    pass
assert "am_cli_test_provider" not in sys.modules, "listing verbs imported a provider"
print("clean")
"""


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A throwaway venv holding exactly the umbrella and the fixture provider."""
    uv = shutil.which("uv")
    if uv is None:  # pragma: no cover - environment-dependent
        pytest.skip("uv is not on PATH; this test installs packages the way CI and users do")

    workspace = tmp_path_factory.mktemp("installed")
    dist = workspace / "dist"
    _run([uv, "build", "--wheel", "--out-dir", str(dist)], cwd=REPO_ROOT)
    (wheel,) = dist.glob("*.whl")

    venv = workspace / "venv"
    _run([uv, "venv", str(venv)])
    env = {**os.environ, "VIRTUAL_ENV": str(venv)}
    _run([uv, "pip", "install", str(wheel), str(PROVIDER)], env=env)
    return venv


def test_a_third_party_distribution_contributes_a_working_verb(installed: Path) -> None:
    """The contract's whole point: a package this repo has never heard of adds a command."""
    result = _cli(installed, "demo", "hello", "--shout")
    assert result.returncode == 0
    assert result.stdout.strip() == "HELLO"


def test_the_verbs_exit_status_survives_the_process_boundary(installed: Path) -> None:
    assert _cli(installed, "demo", "x", "--exit-code", "7").returncode == 7


def test_the_passthrough_adapter_forwards_its_tail(installed: Path) -> None:
    """Style 2 — the cheap on-ramp for a component that already has `main(argv) -> int`. Pinned
    here because argparse.REMAINDER is quirky enough that component authors should copy something
    known to work rather than rediscover it."""
    result = _cli(installed, "passthrough", "score", "--flag", "sim")
    assert result.returncode == 0
    assert result.stdout.strip() == "component ran score with flag=sim"


def test_listing_verbs_imports_no_provider(installed: Path) -> None:
    """The laziness guarantee, in a clean interpreter. Nothing else would catch a regression:
    an eager `load()` produces correct output, just slower and with the whole platform imported."""
    result = _run([str(installed / "bin" / "python"), "-c", _NO_IMPORT_PROBE], check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("clean")


def test_help_lists_the_third_party_verb_with_its_provider(installed: Path) -> None:
    """A verb the manifest knows nothing about is still listed — described from its distribution
    metadata, which is free, rather than from its Subcommand, which would cost an import."""
    result = _cli(installed, "--help")
    assert result.returncode == 0
    assert "demo" in result.stdout
    assert "am-cli-test-provider 0.1.0" in result.stdout


def test_a_malformed_provider_is_reported_as_a_packaging_bug(installed: Path) -> None:
    result = _cli(installed, "malformed")
    assert result.returncode == 2
    assert "does not satisfy the astro_mine.cli contract" in result.stderr
    assert "am-cli-test-provider" in result.stderr
    assert "Traceback" not in result.stderr


def test_python_m_is_equivalent_to_the_console_script(installed: Path) -> None:
    """Container entrypoints and `uv run` reach for the module form; it must not rot."""
    result = _run(
        [str(installed / "bin" / "python"), "-m", "astro_mine.cli", "demo", "hi"], check=False
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "hi"


def test_the_umbrella_still_pulls_in_nothing(installed: Path) -> None:
    """The venv holds the umbrella, the fixture provider, and nothing else — the zero-dependency
    rule checked against a real resolver rather than against our own metadata."""
    uv = shutil.which("uv")
    assert uv is not None
    listing = _run(
        [uv, "pip", "list", "--format", "json"],
        env={**os.environ, "VIRTUAL_ENV": str(installed)},
    )
    names = {package["name"] for package in json.loads(listing.stdout)}
    assert names == {"astro-mine-cli", "am-cli-test-provider"}


def _cli(venv: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run([str(venv / "bin" / "astro-mine"), *args], check=False)


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:  # pragma: no cover - surfaced only on failure
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise AssertionError(f"command failed: {' '.join(command)}")
    return result
