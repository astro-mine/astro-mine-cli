"""Tier-1 training entrypoint + the RayJob entrypoint (RM-P1-LEARN-04; learn.md §2.1, §7).

The one command a `pip install`ed researcher runs to train a baseline on a single
workstation with no cloud (learn.md §7 tier 1), and — unchanged — the entrypoint Cloud wraps
in a KubeRay ``RayJob`` for scale-out (cloud.md). It selects the rollout executor from the
``TrainConfig`` fidelity axis (in-process :class:`LocalExecutor`, distributed
:class:`KubeRayExecutor`, or batched :class:`~astro_mine.learn.envs.vector.VectorExecutor`) —
"the same code with a different executor, never a fork" — trains the chosen baseline, and
emits the learning curve + throughput + the produced-policy provenance.

Learn never imports Cloud. Cloud injects its reproducibility envelope — the **RunContext**
(cloud.md: MLflow run id, image digest, Core interface version, lockfile, input hashes) — as
environment variables; this module *reads* that envelope (:class:`RunContext.from_env`) and
folds it into the produced policy's Core :class:`~astro_mine.core.registry.Provenance`
(:func:`apply_run_context`), completing the build-time + run-time reproducibility chain.

The world is supplied as an importable ``module:attr`` zero-arg **env factory** (``--env-factory``)
that yields either a :class:`~astro_mine.learn.envs.SwarmEnv` or the Core-typed
``(Environment, {AgentId: Asset})`` pair a Learn-free producer hands over — so the entrypoint
stays Sim-free (a real run points it at a Sim-backed factory; the CI smoke points it at the fake
world). The pair form is what lets the producing package avoid importing Learn while still
supplying the SADF the per-agent spaces are derived from.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from astro_mine.learn.algos import TrainConfig


# The training loop, the executor and the provenance stamping stay in the platform: they are
# what this command *calls*, not what it is. Imported inside the handlers rather than at module
# scope so `astro-mine learn --help` does not pay for Ray and Torch (astro-mine-cli#12).
def _build_config(args: argparse.Namespace) -> TrainConfig:
    if args.config_json is not None:
        with open(args.config_json, encoding="utf-8") as handle:
            return TrainConfig.model_validate_json(handle.read())
    overrides: dict[str, Any] = {
        "seed": args.seed,
        "iterations": args.iterations,
        "rollout_steps": args.rollout_steps,
        "fidelity": args.fidelity,
        "num_workers": args.num_workers,
    }
    if args.hidden_sizes is not None:
        overrides["hidden_sizes"] = tuple(int(h) for h in args.hidden_sizes.split(","))
    return TrainConfig(**overrides)


def add_train_arguments(parser: argparse.ArgumentParser) -> None:
    """Every flag `train` takes — attached to both this CLI and the umbrella's.

    Declared once so `astro-mine learn` and the umbrella's `astro-mine train` (RFC-0011 §3, wired
    in :mod:`astro_mine.learn.umbrella`) cannot drift apart. This CLI is flat — no subcommands —
    so the whole parser *is* the verb, and the umbrella attaches the identical set.
    """
    from astro_mine.learn.train.run import DEFAULT_EXPORT_VERSION

    parser.add_argument("--algorithm", default="mappo", help="registered algorithm tag/name")
    parser.add_argument(
        "--env-factory",
        required=True,
        help="importable 'module:attr' zero-arg SwarmEnv factory (a Sim-backed Core world)",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--rollout-steps", type=int, default=32)
    parser.add_argument(
        "--hidden-sizes", default=None, help="comma-separated MLP widths, e.g. 64,64"
    )
    parser.add_argument(
        "--fidelity",
        default="sim_high",
        choices=["sim_high", "surrogate", "gpu_vectorized"],
        help="rollout fidelity tier for this run / curriculum stage",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=1,
        help="KubeRay rollout workers / vector env copies (1 = tier-1 in-process)",
    )
    parser.add_argument(
        "--ray-address",
        default=os.environ.get("RAY_ADDRESS"),
        help="Ray cluster address for a distributed run (default $RAY_ADDRESS)",
    )
    parser.add_argument(
        "--batched-world",
        default=None,
        help=(
            "importable 'module:attr' zero-arg BatchedWorld factory for --fidelity "
            "gpu_vectorized (Sim's Brax/MJX GPU tier, or a JAX surrogate). Without it the "
            "vector executor falls back to the sequential CPU loop."
        ),
    )
    parser.add_argument(
        "--config-json", default=None, help="path to a TrainConfig JSON (overrides flags)"
    )
    parser.add_argument(
        "--output", default=None, help="write the run report JSON here (default stdout)"
    )
    parser.add_argument(
        "--export",
        default=None,
        # Resolved at parse time so the store path is absolute everywhere downstream — the stored
        # sidecar records a `file://` URI, and the paths this command prints should name one place
        # unambiguously. Relative values are accepted and normalized (#33).
        type=lambda value: str(Path(value).resolve()),
        metavar="DIR",
        help=(
            "export the trained policy into this content-addressed store directory "
            "(<dir>/<hex>/{model.onnx,policy_package.json}, one entry per agent). Relative paths "
            "are resolved. Needs the [export] extra"
        ),
    )
    parser.add_argument(
        "--export-format",
        default="onnx",
        choices=["onnx"],
        help="exported artifact format; ONNX is the only cross-component policy artifact",
    )
    parser.add_argument(
        "--export-version",
        default=DEFAULT_EXPORT_VERSION,
        help=f"semver stamped on the exported PolicyPackage (default {DEFAULT_EXPORT_VERSION})",
    )


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = __doc__
    add_train_arguments(parser)


# NOT COVERED, deliberately. Runs a real training job: imports Ray and Torch
# and rolls episodes. The parts
# that are CLI -- `_build_config` and the argument tree -- are tested directly.
def run_from_args(args: argparse.Namespace) -> int:  # pragma: no cover
    """Train from already-parsed arguments; returns the process exit code.

    Split out of :func:`main` so the parsing and the work are separable: the umbrella owns the
    parser on its surface (`astro-mine train`, RFC-0011 §3, wired in
    :mod:`astro_mine.learn.umbrella`), and this is the half it needs. `main` is now
    parse-then-call, so both surfaces run identical code rather than a copy that can drift.
    """
    from astro_mine.learn.train.run import (
        RunContext,
        export_trained_policy,
        resolve_batched_world,
        resolve_env_factory,
        train,
    )

    config = _build_config(args)
    env_factory = resolve_env_factory(args.env_factory)
    report, export = train(
        args.algorithm,
        env_factory,
        config,
        run_context=RunContext.from_env(),
        ray_address=args.ray_address,
        batched_world=resolve_batched_world(args.batched_world),
    )
    # Export before emitting the report: a failed equivalence gate must exit non-zero, and it
    # would be dishonest to have already printed a report announcing a policy that no consumer
    # can load.
    written = (
        export_trained_policy(export, args.export, version=args.export_version)
        if args.export is not None
        else []
    )
    payload = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.output is not None:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload)
    else:
        print(payload)
    for agent, digest, onnx_path in written:
        # The graph digest *is* the artifact identity — carry it to `hub publish` or a
        # leaderboard submission (conventions.md §5).
        print(f"exported {agent}: {digest} -> {onnx_path}", file=sys.stderr)
    return 0


class _Command:
    """`astro-mine learn <verb>` — train a policy and export it."""

    name = "learn"
    help = "train a policy and export it"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        _add_arguments(parser)

    def run(self, args: argparse.Namespace) -> int:
        return run_from_args(args)


command = _Command()
