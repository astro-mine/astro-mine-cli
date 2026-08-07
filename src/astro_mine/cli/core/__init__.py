"""``astro-mine core validate`` — a checker for the Core-authored file formats.

Core owns nine hand-authored formats (SADF, ObjectiveSpec, MissionSpec, Plan/ContingentPlan,
plugin manifest, PolicyPackage, RunProvenance, the units vocabulary, the message catalog) and
until now shipped **no CLI** — a user authoring one of them had no way to ask "is this valid?"
short of writing Python. This module is the shell over the validators Core already ships
(``core.md §1``: *"types and validators"*), and it adds **no** new dependency: ``jsonschema``,
``pydantic``, ``pyyaml`` and ``referencing`` are all already Core dependencies.

**Dispatch is derived from the schema registry, never hand-maintained.** The set of known kinds,
their ``$id``s, and the schemas they validate against all come from
:data:`astro_mine.core.schemas.CORE_JSON_SCHEMAS` and :func:`astro_mine.core.schema_registry`
(RFC-0009). There is no ``{kind: filename}`` map here — that is exactly the fourth-inventory drift
the #50/#52/#53 cluster was about. Adding a tenth Core schema needs no change to this file; a test
(``tests/test_cli.py``) pins that.

**Honesty over a false pass.** A wrong-schema pass is worse than no checker, because it certifies a
document nobody validated. So the CLI never guesses a schema by *resemblance*: a document that
neither declares its ``$schema``, nor identifies itself completely (below), nor is given an
explicit ``--kind`` fails with the list of known kinds. And the two ``$defs``-only *vocabulary*
schemas (``units``, ``messages``) do not constrain a top-level document at all — validating a file
against them would pass anything — so they are not offered as document kinds; the authored message
documents (``action_batch``, ``contact_plan``) are.

**Two ways a document can be self-describing, because one is not always available.** A ``$schema``
pointer is the direct way. But a Core schema is ``additionalProperties: false`` at its root, so a
SADF document **cannot carry one** — the pointer that would identify it is the one key its own
format forbids. Requiring it would mean no SADF file on disk is routable by ``astro-mine validate``
(RFC-0011 §6), which is exactly the state this module was in. So a document is also accepted as
self-describing when it carries **every** root property its schema marks required **and** the
``<format>_version`` discriminator matches that schema's ``const`` exactly.

That is identification, not resemblance, and the difference is the whole of the rule. ``{"
objective_version": "0.1"}`` still fails — it *looks* like an objective and is not one, missing the
``objective`` member the format requires — and a test pins that it keeps failing. What passes is a
document that states which format and version it is, in that format's own required vocabulary, and
carries the structure to back the claim. Guard and Mind already route their formats this way
(``safety_version``, ``stack_spec_version``); this is the same rule, made stricter by also
demanding the rest of the required root.

The dispatch functions (:func:`iter_kinds`, :func:`resolve_kind`, :func:`validate_document`) are
importable so the umbrella ``astro-mine validate`` (RFC-0011) can route into them as a thin call
rather than a rewrite.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

import yaml

__all__ = [
    "Issue",
    "Kind",
    "iter_kinds",
    "main",
    "resolve_kind",
    "validate_document",
    "validate_source",
]

# JSON Schema keywords that constrain an *instance* (as opposed to ``$defs``/metadata, which only
# hold reusable subschemas). A schema declaring none of these — like the ``units`` and ``messages``
# vocabularies — accepts any document at the top level, so it is not a standalone document format.


# --------------------------------------------------------------------------- CLI


# The checker itself is the platform's (astro_mine.core.validation). This module reads the
# arguments and prints the result; it does not decide what a valid document is.
from astro_mine.core.validation import (
    Issue,
    Kind,
    KindError,
    iter_kinds,
    resolve_kind,
    validate_document,
    validate_source,
)


def _cmd_validate(args: argparse.Namespace) -> int:
    results: list[dict[str, Any]] = []
    failed = False
    for path in args.file:
        try:
            source = _read(path)
        except OSError as exc:
            failed = True
            _emit(args, path, None, [Issue("io", str(exc))], results)
            continue
        try:
            kind, issues = validate_source(source, args.kind)
        except (KindError, ValueError) as exc:
            failed = True
            _emit(args, path, None, [Issue("dispatch", str(exc))], results)
            continue
        if issues:
            failed = True
        _emit(args, path, kind, issues, results)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    return 1 if failed else 0


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _emit(
    args: argparse.Namespace,
    path: str,
    kind: Kind | None,
    issues: list[Issue],
    sink: list[dict[str, Any]],
) -> None:
    ok = not issues
    if args.json:
        sink.append(
            {
                "file": path,
                "kind": kind.slug if kind else None,
                "valid": ok,
                "issues": [issue.to_json() for issue in issues],
            }
        )
        return
    label = kind.slug if kind else "?"
    if ok:
        print(f"OK  {path}: valid {label}")
    else:
        print(f"FAIL {path}: {label}", file=sys.stderr)
        for issue in issues:
            print(issue.render(), file=sys.stderr)


def _cmd_kinds(args: argparse.Namespace) -> int:
    if args.json:
        print(
            json.dumps([{"kind": k.slug, "schema_id": k.schema_id} for k in iter_kinds()], indent=2)
        )
    else:
        width = max((len(k.slug) for k in iter_kinds()), default=0)
        for kind in iter_kinds():
            print(f"{kind.slug:<{width}}  {kind.schema_id}")
    return 0


def add_validate_arguments(parser: argparse.ArgumentParser) -> None:
    """`validate`'s own arguments — attached to both this CLI and the umbrella's.

    Declared once so `astro-mine core validate` and `astro-mine validate` (RFC-0011 §3, wired in
    :mod:`astro_mine.core.umbrella`) cannot drift apart. Note that ``--json`` is *not* here: it is
    a top-level flag on this parser, and the umbrella adapter re-adds it per verb, because on the
    umbrella surface a component has no top level to hang it from.
    """
    parser.add_argument("file", nargs="+", help="path to a JSON/YAML document ('-' for stdin)")
    parser.add_argument(
        "--kind",
        help="format to validate against (default: infer from the document's $schema). "
        "Run 'astro-mine core kinds' for the list.",
    )


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        "Validate Core-authored file formats (SADF, ObjectiveSpec, MissionSpec, "
        "Plan, plugin manifest, PolicyPackage, RunProvenance, message documents)."
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate one or more documents")
    add_validate_arguments(validate)
    validate.set_defaults(func=_cmd_validate)

    kinds = sub.add_parser("kinds", help="list the known formats and their schema $ids")
    kinds.set_defaults(func=_cmd_kinds)


class _Command:
    """`astro-mine core <verb>` — validate Core-authored formats; list them."""

    name = "core"
    help = "validate Core-authored formats; list them"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        _add_arguments(parser)

    def run(self, args: argparse.Namespace) -> int:
        return int(args.func(args))


command = _Command()


class _CoreValidator:
    """Core's half of the federated `astro-mine validate`."""

    name = "core"

    def claims(self, path: str) -> str | None:
        """Resolve the document's kind from its ``$schema``/``$id``, or decline it.

        Unreadable or unparseable files are declined rather than claimed: at claim time nobody has
        agreed to own the file yet, so raising here would turn *another* component's malformed
        document into a Core traceback.
        """

        try:
            with open(path, encoding="utf-8") as handle:
                document = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError):
            return None
        if not isinstance(document, dict):
            return None
        try:
            return str(resolve_kind(document, None).slug)
        except KindError:
            return None

    def validate(self, paths: Sequence[str], *, as_json: bool) -> int:
        """Run the same checker `astro-mine core validate` runs — not a second implementation."""
        return int(_cmd_validate(argparse.Namespace(file=list(paths), kind=None, json=as_json)))


validator = _CoreValidator()
