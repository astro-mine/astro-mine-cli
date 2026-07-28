"""`astro-mine studio serve` — the design studio's backend.

**This command cannot run in this distribution, and says so.** `serve` composes the FastAPI
app from :func:`astro_mine.studio.api.create_app`, and the Studio REST surface is deliberately
not part of `astro-mine-platform` (`docs/CONSOLIDATION_PLAN.md` §"Not migrated"). So the verb
exists, its flags are the real ones, and running it reports exactly what to install.

The group is kept rather than dropped because the error message *is* the useful behaviour:
removing `studio` would make `astro-mine --help` claim the platform has less than it does, and
a user following a tutorial would get "unknown component" instead of the one line that tells
them where the REST surface lives.

Everything else that used to live here -- `build_serve_app`, `_wire_hub_seams`, `_mount_ui`,
`render_banner` -- came across in the port and was 113 statements of app composition for an
import that does not resolve. It belongs with the REST surface, wherever that ships, not in a
CLI that cannot reach it (astro-mine-cli#12).
"""

from __future__ import annotations

import argparse
import sys

__all__ = ["command"]

# The environment variables and key-file names `serve` documents in its own --help.
# Kept because they are part of the command's stated contract, and the parity fixture
# records the help strings that name them.
REGISTRY_ENV = "ASTRO_MINE_HUB_REGISTRY"
TRUSTED_KEY_ENV = "ASTRO_MINE_STUDIO_TRUSTED_KEY"
SIGNING_KEY_ENV = "ASTRO_MINE_STUDIO_SIGNING_KEY"
CACHE_DIR_ENV = "ASTRO_MINE_STUDIO_CACHE"
DEFAULT_TRUSTED_KEY_NAMES = ("cosign.pub", "anchor-dev.pub.pem")
DEFAULT_SIGNING_KEY_NAMES = ("cosign.key", "anchor-dev.key.pem")

_UNAVAILABLE = (
    "astro-mine studio serve needs the Studio REST surface (astro_mine.studio.api), which is "
    "not included in astro-mine-platform.\n"
    "  pip install astro-mine-studio[serve]"
)


def _cmd_serve(args: argparse.Namespace) -> int:
    """Report where the REST surface lives. Exit 0: the user asked a fair question."""
    print(_UNAVAILABLE, file=sys.stderr)
    return 0


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        "Astro-Mine Studio — the design front door."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="compose and serve a local Studio (backend + UI)")
    serve.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="bind port (default: 8000)")
    serve.add_argument(
        "--registry",
        default=None,
        help=f"local OCI-layout registry path (default: ${REGISTRY_ENV})",
    )
    serve.add_argument(
        "--trusted-key",
        default=None,
        help=f"PEM public key that pulled content is verified against "
        f"(default: <registry>/keys/{DEFAULT_TRUSTED_KEY_NAMES[0]} or ${TRUSTED_KEY_ENV})",
    )
    serve.add_argument(
        "--signing-key",
        default=None,
        help=f"PEM private key published campaigns are signed with "
        f"(default: <registry>/keys/{DEFAULT_SIGNING_KEY_NAMES[0]} or ${SIGNING_KEY_ENV})",
    )
    serve.add_argument(
        "--cache-dir", default=None, help=f"materialized-content cache (${CACHE_DIR_ENV})"
    )
    serve.add_argument(
        "--ui-dir", default=None, help="built UI directory (default: <cwd>/ui/dist-harness)"
    )
    serve.add_argument("--no-ui", action="store_true", help="do not mount the UI")
    serve.add_argument(
        "--no-seed",
        dest="seed",
        action="store_false",
        help="do not open on the seeded example study",
    )
    serve.set_defaults(seed=True, func=_cmd_serve)


class _Command:
    """`astro-mine studio <verb>` — the design studio."""

    name = "studio"
    help = "the design studio"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        _add_arguments(parser)

    def run(self, args: argparse.Namespace) -> int:
        return int(args.func(args))


command = _Command()
