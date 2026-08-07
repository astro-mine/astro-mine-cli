"""The claims that only a real installation can prove.

Everything else in this suite injects entry points, which is fast and precise but shares one
blind spot: it never exercises the packaging metadata that makes the whole mechanism work in the
first place. So this module does it the long way — build the wheel, create an empty virtualenv,
install the umbrella plus the platform it requires and an unrelated third-party distribution, and
drive the console script as a user would.

Three claims live or die here:

* **No PR to extend** (RFC-0011 §3) — ``am-cli-test-provider`` is not an ``astro-mine-*`` package
  and this repo contains no reference to its verbs or its scaffold kinds, yet ``astro-mine demo``
  and ``astro-mine new demo-doc`` both work.
* **Listing imports nothing** (RFC-0011 §1a) — asserted in a clean interpreter, where a stray
  import cannot be masked by another test having already imported the module.
* **A scaffolded plugin is a real plugin** (RFC-0011 §7) — ``astro-mine plugin new cli`` writes a
  package that installs, registers, and is discovered through its entry-point group. Nothing short
  of installing it proves that, and it is the acceptance criterion the feature stands on.

Marked ``integration`` because it shells out and builds; it is not deselected in CI, where these
are the properties most worth defending.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

# This lane builds a wheel and installs it into a throwaway venv -- the only place this
# package's packaging metadata (the console script, and entry-point discovery *across*
# distributions) is exercised for real.
#
# It was skipped for a while on the grounds that it needed the platform "resolvable from a git
# pin". That diagnosis was wrong, and the skip outlived the issue it named. The pin has been in
# `[tool.uv.sources]` since consolidation; what actually breaks is narrower and does not go away
# on its own: **`uv pip install` does not read `[tool.uv.sources]`**. That table is project
# (workspace) configuration, and the wheel this lane builds carries only
# `Requires-Dist: astro-mine-platform` -- metadata has nowhere to put a git URL. The platform is
# private and on no index, so resolving the wheel's own dependency fails outright.
#
# So the venv is given the platform explicitly, from the very pin `pyproject.toml` declares
# (`_platform_requirement`). That is not a weakening: it is what a user receives from an index
# once the platform publishes, and it is read from the pin rather than duplicated, so the two
# cannot drift. `--no-deps` *would* have been a weakening -- it would let this pass while proving
# something less than it claims, and proving it is the one thing this lane is for.

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
def wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The umbrella, built the way a user would receive it. Built once for the whole module."""
    if shutil.which("uv") is None:  # pragma: no cover - environment-dependent
        pytest.skip("uv is not on PATH; these tests install packages the way CI and users do")
    dist = tmp_path_factory.mktemp("dist")
    _run(["uv", "build", "--wheel", "--out-dir", str(dist)], cwd=REPO_ROOT)
    (built,) = dist.glob("*.whl")
    return built


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory, wheel: Path) -> Path:
    """A throwaway venv holding the umbrella, the platform it requires, and the fixture provider."""
    venv = tmp_path_factory.mktemp("installed") / "venv"
    _install(venv, str(wheel), str(PROVIDER))
    return venv


def _platform_requirement() -> str:
    """The platform as an installable requirement, read from the pin this package already declares.

    One pin, one place. Hard-coding the URL here would create a second copy that silently rots the
    first time `[tool.uv.sources]` moves -- and it moves whenever the platform makes a breaking
    change this package has to follow, which is exactly when a stale copy would resolve a platform
    whose API no longer matches the wheel under test.
    """
    pin = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    source = pin["tool"]["uv"]["sources"]["astro-mine-platform"]
    return f"astro-mine-platform @ git+{source['git']}@{source['rev']}"


def _install(venv: Path, *packages: str) -> None:
    """Create `venv` and install the platform plus `packages` into it, as a user's index would."""
    _run(["uv", "venv", str(venv)])
    _run(
        ["uv", "pip", "install", _platform_requirement(), *packages],
        env={**os.environ, "VIRTUAL_ENV": str(venv)},
    )


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


def test_the_umbrella_pulls_in_the_platform_and_no_other_astro_mine_distribution(
    installed: Path,
) -> None:
    """One wheel behind the umbrella, not eighteen — the consolidation rule, checked against a real
    resolver rather than against our own metadata.

    This assertion used to read `names == {"astro-mine-cli", "am-cli-test-provider"}`, from when
    this package had no dependencies at all. Consolidation dissolved that premise deliberately
    (`pyproject.toml` §dependencies): the platform is one wheel carrying every component, so
    depending on it costs an install that already exists. What is still worth defending is the
    *shape* — `astro-mine-cli` requires `astro-mine-platform` and nothing else of ours. A
    resurrected `astro-mine-<component>` distribution arriving as a transitive dependency is the
    regression the four-distribution rule exists to prevent (`conventions.md` §7.1), and it would
    show up here first.
    """
    uv = shutil.which("uv")
    assert uv is not None
    listing = _run(
        [uv, "pip", "list", "--format", "json"],
        env={**os.environ, "VIRTUAL_ENV": str(installed)},
    )
    names = {package["name"] for package in json.loads(listing.stdout)}
    assert {name for name in names if name.startswith("astro-mine")} == {
        "astro-mine-cli",
        "astro-mine-platform",
    }
    assert "am-cli-test-provider" in names


def test_a_third_party_distribution_contributes_a_scaffold_kind(
    installed: Path, tmp_path: Path
) -> None:
    """The no-PR-to-extend rule for scaffolds (RFC-0011 §7). `demo-doc` appears nowhere in this
    package's source — the umbrella learns of it from installed metadata and routes to its owner."""
    out = tmp_path / "authored.yaml"
    result = _cli(installed, "new", "demo-doc", str(out), "--marker", "proved")
    assert result.returncode == 0, result.stderr
    assert out.read_text(encoding="utf-8") == "kind: demo-doc\nmarker: proved\n"


def test_both_scaffold_groups_list_the_third_party_kinds(installed: Path) -> None:
    """Two groups, two listings, one metadata read each — a kind the manifest has never heard of
    is still shown, described from its distribution rather than by loading it."""
    documents = _cli(installed, "new")
    assert documents.returncode == 0
    assert "demo-doc" in documents.stdout
    assert "am-cli-test-provider 0.1.0" in documents.stdout

    plugins = _cli(installed, "plugin", "new")
    assert plugins.returncode == 0
    assert "demo-plugin" in plugins.stdout
    # The umbrella's own kind is listed alongside the third party's, from the same listing.
    assert "cli" in plugins.stdout


def test_a_scaffolded_verb_plugin_installs_registers_and_runs(
    installed: Path, wheel: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The acceptance criterion, end to end and in that order: scaffold, install, discover, run.

    A scaffold that emits something plausible but not installable is worse than none at all — the
    author debugs *our* template before writing a line of their own. So the generated package is
    put into a venv that holds nothing but the umbrella, and the verb it claims to register is
    invoked through the console script exactly as a user would.
    """
    workspace = tmp_path_factory.mktemp("scaffolded")
    package = workspace / "acme-greet"
    scaffolded = _cli(installed, "plugin", "new", "cli", str(package), "--verb", "greet")
    assert scaffolded.returncode == 0, scaffolded.stderr

    venv = workspace / "venv"
    _install(venv, str(wheel), str(package))

    ran = _cli(venv, "greet", "--name", "moon")
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == "hello, moon"
    # Discovered, not merely runnable: it shows up in the listing like any other verb.
    assert "greet" in _cli(venv, "--help").stdout


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
