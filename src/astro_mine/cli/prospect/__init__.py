"""`astro-mine prospect publish` — publish a belief prior to a local Hub registry.

The operator-facing half of RM-P1-PROSPECT-13. The work itself — serializing a prior to the
content-addressed bundle, building the Core ``resource_field_backend`` manifest, storing and
signing it in a **local OCI-layout registry** — is
:func:`astro_mine.prospect.publish.publish_prior` and stays in the platform. This module reads
the arguments, mints a keypair when the user did not bring one, and prints the reference and
digest that came back.

Offline by default: the tier-1 path, no hosted Hub (hub.md principle 7; ``LUNAR-TR-004``).
"""

from __future__ import annotations

import argparse
from pathlib import Path

__all__ = ["command"]

#: The anchor recipe — `astro-mine prospect publish` with no `--name` publishes the lunar
#: polar prior the flagship scenario pins, which is the case worth making a default.
_DEFAULT_RECIPE = "shackleton_water_ice_v1"


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = "Astro-Mine-Prospect tools."
    subparsers = parser.add_subparsers(dest="command", required=True)

    publish = subparsers.add_parser(
        "publish", help="Publish a belief-prior bundle to a local Hub registry."
    )
    publish.add_argument(
        "--registry",
        required=True,
        type=Path,
        help="Local OCI-layout registry path, or a remote registry URL (e.g. ghcr.io/astro-mine).",
    )
    publish.add_argument(
        "--name", default=_DEFAULT_RECIPE, help="Prior recipe to publish (default: the anchor)."
    )
    publish.add_argument(
        "--version", default=None, help="Artifact version (default: the recipe version)."
    )
    publish.add_argument(
        "--private-key",
        type=Path,
        default=None,
        help="ECDSA P-256 signing key (PEM); a fresh keypair is generated if omitted.",
    )
    publish.add_argument(
        "--public-key-out",
        type=Path,
        default=None,
        help="Write the generated public key (PEM) here (only when a key is generated).",
    )
    publish.set_defaults(func=_cmd_publish)


def _cmd_publish(args: argparse.Namespace) -> int:
    from astro_mine.hub.supply_chain import generate_keypair
    from astro_mine.prospect.priors import load_prior
    from astro_mine.prospect.publish import publish_prior

    prior = load_prior(args.name)
    if args.private_key is not None:
        private_pem = args.private_key.read_bytes()
    else:
        private_pem, public_pem = generate_keypair()
        if args.public_key_out is not None:
            args.public_key_out.write_bytes(public_pem)
    artifact = publish_prior(
        prior,
        registry_path=args.registry,
        private_key_pem=private_pem,
        version=args.version,
    )
    print(f"published {artifact.reference} -> {artifact.digest}")
    return 0


class _Command:
    """`astro-mine prospect <verb>` — publish resource priors."""

    name = "prospect"
    help = "publish resource priors"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        _add_arguments(parser)

    def run(self, args: argparse.Namespace) -> int:
        return int(args.func(args))


command = _Command()
