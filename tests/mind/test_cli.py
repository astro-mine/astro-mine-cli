"""``astro-mine-mind`` CLI — validate / compose / stacks over the shipped reference stacks (G2.6).

The properties the issue is about:

* ``stacks`` enumerates the 6 reference stacks + 13 manifests **from package data** (wheel-safe);
* ``validate`` catches a stack that binds an **unregistered plugin**, naming the entry-point group
  and the missing name — the failure a shape-only validator misses;
* ``compose`` reports tier → plugin → **version**;
* there is **no ``run``** — stepping a stack needs a Core Environment Mind does not provide.
"""

from __future__ import annotations

from astro_mine.cli import mind as cli

# Migrated from astro-mine-platform, where these drove `astro-mine-mind <verb>` directly.
# The commands did not change -- only their address -- so the bodies are untouched and this
# shim re-points `main([...])` at the one executable: `astro-mine mind <verb>`.
from astro_mine.cli import main as _astro_mine


def main(argv=None):  # type: ignore[no-untyped-def]
    return _astro_mine(["mind", *(argv or [])])


from importlib import resources
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
_REFERENCE = "astro_mine.mind.reference"


# --------------------------------------------------------------------------- package data


def test_stacks_enumerates_package_data() -> None:
    stacks = list(cli.iter_stack_resources())
    manifests = list(cli.iter_manifest_resources())
    assert len(stacks) == 6, stacks
    assert len(manifests) == 13, manifests
    assert "lunar_prospecting.yaml" in stacks
    assert "lunar_prospecting_anchor.yaml" in stacks


def test_stacks_command_lists_counts(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["stacks"]) == 0
    out = capsys.readouterr().out
    assert "reference stacks (6)" in out
    assert "reference manifests (13)" in out


# --------------------------------------------------------------------------- validate




def test_validate_names_unregistered_plugin(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = yaml.safe_load(
        resources.files(_REFERENCE).joinpath("stacks/lunar_prospecting.yaml").read_text()
    )
    doc["stack_spec"]["tiers"][0]["plugin"] = "no.such.plugin"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(doc), encoding="utf-8")

    assert main(["validate", str(bad)]) == 1
    err = capsys.readouterr().err
    assert "no.such.plugin" in err
    assert "astro_mine.mind.tier_plugins" in err  # the group is named


def test_validate_fails_on_bad_schema(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("stack_spec_version: '0.1'\nstack_spec: {}\n", encoding="utf-8")
    assert main(["validate", str(bad)]) == 1


def test_validate_multiple_files_exit_nonzero_if_any_fails(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: a stack\n", encoding="utf-8")
    assert main(["validate", "lunar_prospecting.yaml", str(bad)]) == 1


# --------------------------------------------------------------------------- compose


def test_compose_reports_tier_plugin_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["compose", "lunar_prospecting.yaml"]) == 0
    out = capsys.readouterr().out
    assert "mind.reference.mission @" in out
    assert "shield" in out
    assert "astro_mine.mind.tier_plugins" in out
    assert "core interface versions:" in out


def test_compose_behavior_tree_stack(capsys: pytest.CaptureFixture[str]) -> None:
    # A behavior-tree-execution stack composes by auto-resolving the packaged reference tree.
    assert main(["compose", "lunar_prospecting_bt.yaml"]) == 0
    assert "execution: behavior_tree" in capsys.readouterr().out


# --------------------------------------------------------------------------- no run verb


def test_no_run_verb() -> None:
    # `run` is deliberately absent — a real episode needs a Core Environment (Sim). argparse exits 2
    # on an unknown subcommand.
    with pytest.raises(SystemExit) as excinfo:
        main(["run", "lunar_prospecting.yaml"])
    assert excinfo.value.code == 2


# --------------------------------------------------------------------------- the wheel boundary


