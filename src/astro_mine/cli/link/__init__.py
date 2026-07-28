"""`astro-mine link publish` — publish a contact plan to a Hub registry.

The operator-facing half of the Link→Hub path (link.md §6): it pushes a serialized
:class:`~astro_mine.core.messages.ContactPlan` to a **local OCI-layout** registry (or a remote
one, e.g. ``ghcr.io/astro-mine``) as a signed ``comms_model`` artifact and prints its content
digest — the value a Bench ``ScenarioSpec`` pins. The cosign ECDSA-P256 key that signs it comes
from ``astro-mine hub keygen``, the one signing-key command. Offline by default: no hosted Hub,
no Cloud (hub.md principle 7; ``LUNAR-TR-004``).

The plan itself is produced by the library and handed here in Core's byte-stable wire form, so
this command never re-derives geometry — it publishes bytes it was given. That is the whole of
the thin-wrapper rule in one command: read the arguments, call
:func:`astro_mine.link.registry.publish_contact_plan`, print what came back.

Backlog: RM-P0-LINK-04.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

__all__ = ["command"]


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = "Astro-Mine-Link tools."
    sub = parser.add_subparsers(dest="command", required=True)

    publish = sub.add_parser(
        "publish", help="Publish a ContactPlan to a local OCI-layout Hub registry."
    )
    publish.add_argument("plan", type=Path, help="ContactPlan in Core wire form (.pb).")
    publish.add_argument(
        "--registry",
        required=True,
        help="Local OCI-layout registry path, or a remote registry URL (e.g. ghcr.io/astro-mine).",
    )
    publish.add_argument("--name", required=True, help="Artifact name (the stable content id).")
    publish.add_argument("--version", required=True, help="Artifact version (SemVer).")
    publish.add_argument(
        "--scenario-id", required=True, help="The scenario this comms model belongs to."
    )
    publish.add_argument(
        "--key",
        type=Path,
        required=True,
        help=(
            "Cosign ECDSA-P256 private key (PEM); signs the artifact. Required — Hub admits no "
            "unsigned content. Mint one with `astro-mine hub keygen`."
        ),
    )
    publish.add_argument(
        "--input-hashes",
        type=Path,
        default=None,
        help="JSON object of pinned-input digests (kernels/terrain/nodes/epoch/config).",
    )
    publish.set_defaults(func=_publish)


def _publish(args: argparse.Namespace) -> int:
    from astro_mine.core.messages import contact_plan_from_wire
    from astro_mine.link.registry import publish_contact_plan

    plan = contact_plan_from_wire(Path(args.plan).read_bytes())
    input_hashes: dict[str, str] = {}
    if args.input_hashes is not None:
        loaded: Any = json.loads(Path(args.input_hashes).read_text())
        input_hashes = {str(k): str(v) for k, v in dict(loaded).items()}
    private_key_pem = Path(args.key).read_bytes()

    artifact = publish_contact_plan(
        plan,
        registry_path=args.registry,
        name=args.name,
        version=args.version,
        scenario_id=args.scenario_id,
        input_hashes=input_hashes or None,
        private_key_pem=private_key_pem,
    )
    print(f"published {artifact.reference} -> {artifact.digest}")
    return 0


class _Command:
    """`astro-mine link <verb>` — publish contact plans."""

    name = "link"
    help = "publish contact plans"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        _add_arguments(parser)

    def run(self, args: argparse.Namespace) -> int:
        return int(args.func(args))


command = _Command()
