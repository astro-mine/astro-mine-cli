"""The handler paths the migrated suites never reached.

The 13 suites recovered from the platform cover what those CLIs were *tested* for. They do not
cover everything those CLIs *do* — error branches, optional flags, and the publish/export paths
that the platform's own tests exercised through the library rather than through argv. This file
is the difference.

Each test names a path, not a percentage. Where a path cannot be reached offline (a live
leaderboard, a cluster) it is absent rather than mocked into something that proves nothing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from astro_mine.cli import main

# --- learn: config assembly -----------------------------------------------------------------
#
# `_build_config` turns a Namespace into a TrainConfig. It is the whole of Learn's CLI logic:
# everything after it is the platform's training loop. Called directly because reaching it
# through `astro-mine learn` means importing Ray and Torch and running an episode.


def _learn_args(**overrides: object) -> argparse.Namespace:
    base = dict(
        config_json=None,
        seed=7,
        iterations=1,
        rollout_steps=8,
        fidelity="sim_high",
        num_workers=1,
        hidden_sizes=None,
    )
    return argparse.Namespace(**{**base, **overrides})


def test_learn_config_is_built_from_the_flags() -> None:
    from astro_mine.cli.learn import _build_config

    config = _build_config(_learn_args())
    assert config.seed == 7
    assert config.iterations == 1


def test_learn_hidden_sizes_parses_a_comma_list() -> None:
    """`--hidden-sizes 64,64` is a string on the wire and a tuple in the config."""
    from astro_mine.cli.learn import _build_config

    assert _build_config(_learn_args(hidden_sizes="64,32")).hidden_sizes == (64, 32)


def test_learn_config_json_wins_over_every_flag(tmp_path: Path) -> None:
    """`--config-json` is the whole config, not a set of defaults to merge into.

    A file that only half-applied would be the worst of both: a run whose provenance names a
    config that is not the one that ran.
    """
    from astro_mine.cli.learn import _build_config

    path = tmp_path / "c.json"
    path.write_text(json.dumps({"seed": 999, "iterations": 3}), encoding="utf-8")
    config = _build_config(_learn_args(config_json=str(path), seed=1, iterations=1))
    assert config.seed == 999
    assert config.iterations == 3


# --- prospect: publish ----------------------------------------------------------------------


def test_prospect_publish_mints_a_key_and_writes_the_public_half(tmp_path: Path) -> None:
    """With no `--private-key`, a keypair is generated and `--public-key-out` receives it.

    The offline tier-1 path: a local OCI-layout registry, no hosted Hub, no network.
    """
    registry, pub = tmp_path / "reg", tmp_path / "pub.pem"
    assert (
        main(["prospect", "publish", "--registry", str(registry), "--public-key-out", str(pub)])
        == 0
    )
    assert pub.exists() and b"PUBLIC KEY" in pub.read_bytes()
    assert (registry / "oci-layout").exists()


def test_prospect_publish_accepts_a_key_the_user_brought(tmp_path: Path) -> None:
    from astro_mine.hub.supply_chain import generate_keypair

    private, _ = generate_keypair()
    key = tmp_path / "k.pem"
    key.write_bytes(private)
    assert (
        main(
            ["prospect", "publish", "--registry", str(tmp_path / "reg"), "--private-key", str(key)]
        )
        == 0
    )


# --- new / plugin new: the branches a happy path does not reach -----------------------------


def test_new_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    out = tmp_path / "a.yaml"
    assert main(["new", "asset", str(out)]) == 0
    before = out.read_text(encoding="utf-8")
    assert main(["new", "asset", str(out)]) != 0, "an existing file was silently overwritten"
    assert out.read_text(encoding="utf-8") == before


def test_new_force_overwrites(tmp_path: Path) -> None:
    out = tmp_path / "a.yaml"
    assert main(["new", "asset", str(out)]) == 0
    assert main(["new", "asset", str(out), "--force"]) == 0


def test_bare_new_lists_the_kinds_and_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    """`astro-mine new` with no kind is a question, not a mistake — answer it and exit 0."""
    assert main(["new"]) == 0
    out = capsys.readouterr().out
    assert all(kind in out for kind in ("asset", "world", "stack", "safety"))


def test_bare_plugin_new_lists_the_kinds(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["plugin", "new"]) == 0
    assert "solver" in capsys.readouterr().out


def test_plugin_new_rejects_an_unknown_kind(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["plugin", "new", "nonsense", "/tmp/x"]) == 2
    assert "unknown" in capsys.readouterr().err


def test_new_asset_kind_flag_reaches_the_scaffold(tmp_path: Path) -> None:
    """`--kind excavator` is Fleet's flag, declared by the scaffold rather than by the router."""
    out = tmp_path / "e.yaml"
    assert main(["new", "asset", str(out), "--kind", "excavator"]) == 0
    assert "excavator" in out.read_text(encoding="utf-8")


# --- studio: the command that cannot run here -----------------------------------------------


def test_studio_serve_says_where_the_rest_surface_lives(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The platform does not ship `astro_mine.studio.api`, so this reports rather than crashes.

    The answer has to be *reachable*, which is one half of what was wrong: the message used to
    end with `pip install astro-mine-studio[serve]`, a distribution the consolidation retired
    (astro-mine-cli#19). It now names `astro-mine-api` and the roadmap item that stands it up,
    and says outright that nothing installable exists yet — so the reader stops rather than
    fighting pip. The negative assertion is the one that matters: an install hint is only worth
    printing if it resolves.
    """
    assert main(["studio", "serve"]) != 0
    err = capsys.readouterr().err
    assert "astro_mine.studio.api" in err
    assert "astro-mine-api" in err
    assert "RM-DIST-03" in err
    assert "astro-mine-studio[serve]" not in err
    assert "pip install" not in err


def test_studio_serve_fails_rather_than_reporting_success(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The other half (astro-mine-cli#22): nothing was served, so this is not a success.

    It returned 0 for a while, on the reasoning that the user had asked a fair question and got
    a complete answer. But `serve` is imperative, not interrogative — the *outcome* is that no
    server is running, and exit 0 asserts the opposite to everything that composes the command:

        astro-mine studio serve && open http://localhost:8000     # opened a dead port

    A separate test from the one above on purpose. The message and the status are independent
    regressions with independent causes, and a single test asserting both would let a future
    reader assume fixing one covered the other — which is exactly how these two drifted apart.

    **1, not 2.** 2 is `_dispatch._USAGE_ERROR`, "I typed this wrong". Nothing here is
    mistyped; the distribution is incomplete. Pinned exactly, because "non-zero" is not the
    contract — a script that branches on the code needs the code to be stable.
    """
    assert main(["studio", "serve"]) == 1
    assert capsys.readouterr().err.strip(), "a failing command must still say why"


# --- core: the validate flags the migrated suite does not exercise --------------------------


def test_core_validate_json_output_is_machine_readable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = tmp_path / "a.yaml"
    assert main(["new", "asset", str(doc)]) == 0
    capsys.readouterr()
    assert main(["core", "--json", "validate", str(doc)]) == 0
    assert isinstance(json.loads(capsys.readouterr().out), list)


def test_core_kinds_lists_the_nine_formats(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["core", "kinds"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) >= 9


def test_core_kinds_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["core", "--json", "kinds"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows and {"kind", "schema_id"} <= set(rows[0])


def test_core_validate_names_the_kind_it_was_told(tmp_path: Path) -> None:
    """`--kind` overrides inference; a document checked against the wrong schema must fail."""
    doc = tmp_path / "a.yaml"
    assert main(["new", "asset", str(doc)]) == 0
    assert main(["core", "validate", "--kind", "objective", str(doc)]) == 1


# --- routers: the branches a happy path does not reach --------------------------------------


def test_plugin_rejects_an_action_that_is_not_new(capsys: pytest.CaptureFixture[str]) -> None:
    """`plugin` has exactly one action. Anything else names what is available."""
    assert main(["plugin", "list"]) == 2
    assert "unknown action" in capsys.readouterr().err


def test_a_third_party_kind_shadowing_a_built_in_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A collision is reported through the verb, not just raised out of discovery.

    `plugin new` owns the `cli` kind itself, so a package claiming it is the case the
    built-in-shadowing branch exists for.
    """
    import astro_mine.cli._scaffolds as scaffolds
    from _verbs import make_entry_point

    real = scaffolds.discover_scaffolds

    def shadowed(group: str, entries=None):  # type: ignore[no-untyped-def]
        return dict(real(group, entries=[make_entry_point("cli", "ECHO", group)]))

    monkeypatch.setattr(scaffolds, "discover_scaffolds", shadowed)
    monkeypatch.setattr("astro_mine.cli._new.discover_scaffolds", shadowed)
    assert main(["plugin", "new", "cli", str(tmp_path / "x")]) == 2
    assert "shadows" in capsys.readouterr().err
