"""`astro-mine studio serve` — the design studio's backend.

**This command cannot run in this distribution, and says so.** `serve` composes the FastAPI
app from :func:`astro_mine.studio.api.create_app`, and the Studio REST surface is deliberately
not part of `astro-mine-platform` (the platform's `docs/CONSOLIDATION_PLAN.md` §"Not migrated";
`architecture/api.md`). So the verb exists, its flags are the real ones, and running it reports
where the surface lives — which is `astro-mine-api`, where it is built and running as
`astro_mine_api.studio`. It does **not** report what to *install*, because no distribution is
published to a package index during incubation; naming one that does not resolve is the defect
this message was fixed for (astro-mine-cli#19). It reports how to *run* it instead, which is a
different thing and is the half `architecture/cli.md` §9 requires.

The group is kept rather than dropped because the error message *is* the useful behaviour:
removing `studio` would make `astro-mine --help` claim the platform has less than it does, and
a user following a tutorial would get "unknown component" instead of the one line that tells
them where the REST surface lives. Useful behaviour, but not *success* — `serve` exits non-zero,
because nothing was served (astro-mine-cli#22; see :data:`_UNAVAILABLE_STATUS`).

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

#: What `serve` prints instead of serving.
#
# The second line used to read `pip install astro-mine-studio[serve]` -- a distribution the
# consolidation retired, so the message named a fix that could not work (astro-mine-cli#19). An
# install hint that resolves to nothing is worse than no hint: it sends the reader to pip, which
# reports "no matching distribution" and leaves them believing their environment is broken.
#
# The honest answer names the distribution that owns the surface and how to reach it. It used to
# say the surface did not exist yet, so a reader would stop looking -- correct while that was
# true, and the whole message when it stopped being true. This comment predicted its own fix:
# "when astro-mine-api ships (RM-DIST-03), this becomes `pip install astro-mine-api`". Both
# halves were wrong. The API shipped -- RM-DIST-03 closed 2026-08-08 and the surface runs as
# `astro_mine_api.studio` -- and `pip install astro-mine-api` still resolves to nothing, because
# nothing is published to an index during incubation.
#
# So the conclusion survived its own premise, and that is the trap: "there is nothing to install"
# stayed true for a different reason, which made the sentence above it look true too. What broke
# was the *other* half of `architecture/cli.md` §9 -- report what is missing **and how to get
# it**. There is now a way to get it, and a message that withholds it is no longer honest
# degradation, it is just a refusal (astro-mine-cli#38).
#
# No roadmap ID here. RM-DIST-03 is closed; pointing a blocked reader at a finished item is the
# same defect wearing different clothes.
_UNAVAILABLE = (
    "astro-mine studio serve needs the Studio REST surface (astro_mine.studio.api), which is "
    "not included in astro-mine-platform.\n"
    "  It is built, and ships in astro-mine-api as astro_mine_api.studio "
    "(docs: architecture/api.md).\n"
    "  No distribution is published to a package index during incubation, so there is nothing "
    "to install.\n"
    "  Run it from a clone of astro-mine-api:\n"
    "    uv run uvicorn --factory astro_mine_api._app:make_app"
)


#: `serve` could not serve, so it does not report success (astro-mine-cli#22).
#
# This used to return 0, on the reasoning that the user "asked a fair question and got a complete
# answer". They did not ask a question -- `serve` is imperative. Answering an imperative with an
# explanation is the right *behaviour*; reporting it as success is a claim about the *outcome*, and
# no server is running. `astro-mine studio serve && open http://localhost:8000` opened a dead port,
# and a CI step that backgrounded it passed.
#
# **1, not 2.** The 2 in `_dispatch._USAGE_ERROR` means "I typed this wrong", kept deliberately
# distinct from the 1-and-up range a command uses for its own failures. Nothing about this
# invocation is malformed -- every flag is real and correctly spelled -- so 2 would point the reader
# at their command line when the problem is their installation. 1 says the run failed, which is what
# happened, and matches `astro-mine hub`'s refusal path.
#
# The message being *good* is what made the old status dangerous rather than obvious: the command
# looked like it had worked and helpfully explained something. A human reading a terminal was fine;
# a Makefile, a compose healthcheck or a tutorial's copy-paste block was not.
_UNAVAILABLE_STATUS = 1


def _cmd_serve(args: argparse.Namespace) -> int:
    """Report where the REST surface lives, and fail: nothing was served."""
    print(_UNAVAILABLE, file=sys.stderr)
    return _UNAVAILABLE_STATUS


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = "Astro-Mine Studio — the design front door."
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
