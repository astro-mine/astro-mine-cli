"""The ``astro-mine seal`` CLI — sign / verify / provenance / sbom / inspect.

A thin argparse front-end over :mod:`astro_mine.seal`, the platform's one home for signing,
verification, SLSA provenance, and SBOM generation (RFC-0005; ``architecture/seal.md``). Seal was
the archetypal command-line tool with no command line: thirteen components shipped a group and the
one that exists to be run from a shell did not, so verifying an artifact someone handed you out of
band meant writing Python or routing through a component that happens to embed the verifier
(astro-mine-cli#17).

Everything here is **offline and accountless** (CX-LOCAL). Seal's signer is keyed ECDSA P-256 with
no Fulcio, Rekor, or OIDC in the path, so every verb works on a laptop with no network.

**What this group is for: loose files.** ``seal`` operates on bytes you have — a file, a digest, a
detached signature, an attestation document. It never opens a registry. Anything addressed by a
registry reference belongs to ``astro-mine hub``.

**Why ``seal verify`` and ``hub verify`` are both verbs.** They answer different questions, and
neither is a wrapper on the other:

* ``astro-mine hub verify <ref> --registry R`` resolves a *published artifact* and runs the full
  verify-twice policy — the stored bytes re-hash to their addresses, every attached signature
  verifies, SLSA provenance and an SBOM are present and well-shaped.
* ``astro-mine seal verify <file> --signature s.json --key k.pub`` checks *one detached signature
  over one file*, with no registry in the picture.

The delegation the issue asked about already exists, one level below the CLI:
``astro_mine.hub.supply_chain`` imports Seal's ``verify`` rather than reimplementing it, so there
is exactly one signature check in the platform. Adding a second delegation between the two commands
would not remove an implementation, only hide which question was asked.

**Two digests, not one.** ``seal sign <file>`` signs the content hash of that file's bytes.
``hub publish`` signs an artifact's *manifest* digest. They are different subjects on purpose, so a
signature made here does not verify a Hub artifact and vice versa — the help says so at both ends.

**No ``keygen`` here.** ``astro-mine hub keygen`` mints the cosign keypair the whole platform uses,
and one documented way to mint a key is worth more than a convenient second one that drifts.

**No ``attest`` here.** :func:`astro_mine.seal.attest` attaches a signature, provenance and an SBOM
to an :class:`~astro_mine.seal.AttestationStore` — a registry. Seal's design keeps it out of the
registry plane (``seal.md`` §1: "storing and serving artifacts is Hub"), and a CLI that opened one
would put it straight back. ``astro-mine hub publish`` attaches; the verbs here emit the three
payloads it attaches, so they can be produced, inspected and archived on their own.

**Bad input is an error, never a traceback** — one ``astro-mine seal <verb>: <what went wrong>``
line on stderr and a non-zero exit, matching ``astro-mine hub``. :class:`_Command.run` carries the
backstop so a new verb cannot reintroduce one.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from astro_mine.core.hashing import canonical_json, content_hash
from astro_mine.core.registry import Signature
from astro_mine.seal import (
    AttestationError,
    SignatureError,
    build_cyclonedx_sbom,
    build_slsa_provenance,
    sign_digest,
    verify_sbom_document,
    verify_signature,
    verify_slsa_document,
)

__all__ = ["command"]

#: A content address, as every Seal and Core surface spells it.
_DIGEST_PREFIX = "sha256:"

#: Where `keygen` lives. Named in three help strings, so it is written once.
_KEYGEN = "astro-mine hub keygen"


class InputError(Exception):
    """A problem with what the user passed in — reported as one line, never as a traceback."""


# --- reading the things a verb is given ---------------------------------------------------------


def _read_bytes(path: str, what: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read {what} {path}: {exc.strerror or exc}") from exc


def _read_json(path: str, what: str) -> Mapping[str, Any]:
    """A JSON *object* from disk. A document that is not one is refused, not coerced."""
    payload = _read_bytes(path, what)
    try:
        document = json.loads(payload)
    except ValueError as exc:
        raise InputError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise InputError(f"{path} is not a JSON object, so it cannot be {what}")
    return document


def _subject(args: argparse.Namespace) -> str:
    """The digest a verb operates on: hashed from ``path``, or passed as ``--digest``.

    Exactly one of the two, enforced here rather than by argparse: a mutually exclusive group
    cannot express "one of these is required" across a positional and an option without making
    the positional optional in a way that reads badly in ``--help``.
    """
    if args.path is not None and args.digest is not None:
        raise InputError("pass a file or --digest, not both")
    if args.digest is not None:
        return _checked_digest(args.digest)
    if args.path is None:
        raise InputError("pass a file to hash, or --digest if you already have its content hash")
    return content_hash(_read_bytes(args.path, "file"))


def _checked_digest(digest: str) -> str:
    """``--digest`` is validated here so a typo is refused rather than signed.

    Seal's own ``_digest_parts`` would catch a malformed digest inside ``build_slsa_provenance``,
    but ``sign_digest`` would happily sign any string — and a signature over ``sha256;abc`` is a
    valid signature over the wrong thing, which is the failure a user is least equipped to notice.
    """
    if not digest.startswith(_DIGEST_PREFIX) or not digest[len(_DIGEST_PREFIX) :]:
        raise InputError(f"{digest!r} is not a content address; expected {_DIGEST_PREFIX}<hex>")
    return digest


def _emit(document: Any, out: str | None, *, what: str) -> int:
    """Write a document to ``--out`` or to stdout, in the platform's canonical byte form.

    :func:`~astro_mine.core.hashing.canonical_json` rather than ``json.dumps``: these documents are
    content-addressed elsewhere in the platform, so the bytes this command writes must be the bytes
    Hub would hash. Pretty-printing them here would make a locally generated attestation and a
    published one differ by whitespace and therefore by digest.
    """
    payload = canonical_json(document)
    if out is None:
        sys.stdout.buffer.write(payload + b"\n")
        return 0
    try:
        Path(out).write_bytes(payload)
    except OSError as exc:
        raise InputError(f"cannot write {out}: {exc.strerror or exc}") from exc
    print(f"wrote {what} to {out}")
    return 0


# --- the verbs ----------------------------------------------------------------------------------


def _cmd_sign(args: argparse.Namespace) -> int:
    """Sign a file's content hash, or a digest, and emit the detached cosign signature."""
    digest = _subject(args)
    signature = sign_digest(digest, _read_bytes(args.key, "signing key"))
    return _emit(signature.model_dump(mode="json"), args.out, what="signature")


def _cmd_verify(args: argparse.Namespace) -> int:
    """Check a detached signature covers this file, and that the trusted key made it.

    Fail-closed and quiet on success: ``ok <digest>``, exit 0. Any failure — a tampered file, a
    signature for a different artifact, a signer that is not the trusted key, a malformed
    envelope — is one line on stderr and exit 1.
    """
    digest = _subject(args)
    document = _read_json(args.signature, "a signature")
    try:
        signature = Signature.model_validate(document)
    except Exception as exc:
        raise InputError(f"{args.signature} is not a Signature document: {exc}") from exc

    verify_signature(signature, digest, trusted_public_key_pem=_read_bytes(args.key, "public key"))
    print(f"ok {digest}")
    return 0


def _cmd_provenance(args: argparse.Namespace) -> int:
    """Emit SLSA v1 provenance binding a subject digest to its builder and resolved inputs."""
    return _emit(
        build_slsa_provenance(
            subject_name=f"{args.name}:{args.version}",
            subject_digest=_subject(args),
            builder_id=args.builder_id,
            inputs=[_checked_digest(value) for value in (args.input or [])],
        ),
        args.out,
        what="provenance",
    )


def _cmd_sbom(args: argparse.Namespace) -> int:
    """Emit a CycloneDX SBOM over the components named on the command line."""
    return _emit(
        build_cyclonedx_sbom(
            name=args.name,
            version=args.version,
            components=[_component(value) for value in (args.component or [])],
        ),
        args.out,
        what="SBOM",
    )


def _component(value: str) -> Mapping[str, str]:
    """``--component name==version`` → the mapping the SBOM builder takes.

    ``==`` rather than ``=`` so a version containing ``=`` is unambiguous, and matching the PEP 440
    pin syntax a reader already associates with "this exact version".
    """
    name, separator, version = value.partition("==")
    if not separator or not name or not version:
        raise InputError(f"--component {value!r} is not `name==version`")
    return {"name": name, "version": version}


#: How :func:`_cmd_inspect` recognizes each document, and what it checks once it has.
#:
#: Keyed on a field the format *defines* rather than on a filename or a flag: a signature carries
#: a ``scheme``, an in-toto statement a ``predicateType``, a CycloneDX SBOM a ``bomFormat``. A
#: document matching none of them is refused rather than guessed at — the same rule
#: ``astro-mine validate`` follows for authored formats.
_INSPECTORS: tuple[tuple[str, str, Any], ...] = (
    ("bomFormat", "SBOM", verify_sbom_document),
    ("predicateType", "SLSA provenance", verify_slsa_document),
)


def _cmd_inspect(args: argparse.Namespace) -> int:
    """Identify an attestation document and check it is well-shaped — fail-closed.

    The reader for evidence handed to you out of band. It answers *what is this, and is it
    intact as a document* — **not** *do I trust it*: a well-shaped SLSA statement proves nothing
    about the artifact it names. Only `verify` (or `astro-mine hub verify`) answers that, and the
    summary says which subject to point it at.
    """
    document = _read_json(args.document, "an attestation document")

    if "scheme" in document:
        try:
            signature = Signature.model_validate(document)
        except Exception as exc:
            raise InputError(f"{args.document} is not a valid Signature: {exc}") from exc
        print(f"signature\tscheme={signature.scheme.value}\tsubject={signature.payload}")
        return 0

    for field, label, check in _INSPECTORS:
        if field not in document:
            continue
        try:
            check(document)
        except AttestationError as exc:
            raise InputError(f"{args.document} is not a valid {label}: {exc}") from exc
        print(f"{label}\t{_summary(label, document)}")
        return 0

    raise InputError(
        f"{args.document} is not a signature, SLSA provenance, or CycloneDX SBOM — "
        f"no `scheme`, `predicateType` or `bomFormat` field"
    )


def _summary(label: str, document: Mapping[str, Any]) -> str:
    """One tab-separated line per document kind, naming the subject a verifier would check."""
    if label == "SBOM":
        component = document.get("metadata", {}).get("component", {})
        count = len(document.get("components", []))
        subject = f"{component.get('name')}@{component.get('version')}"
        return f"subject={subject}\t{count} components"
    subjects = document.get("subject", [])
    name = subjects[0].get("name") if subjects else None
    builder = document.get("predicate", {}).get("runDetails", {}).get("builder", {}).get("id")
    return f"subject={name}\tbuilder={builder}"


# --- per-verb argument sets ---------------------------------------------------------------------
#
# Extracted per verb to match `astro-mine hub`'s layout, which declares each verb's flags once so
# two parsers cannot drift. Seal has one parser today; keeping the shape identical is what makes
# that stay true if it ever gains a second.


def _add_subject_arguments(parser: argparse.ArgumentParser, *, verb: str) -> None:
    """The file-or-digest pair every subject-taking verb shares."""
    parser.add_argument(
        "path",
        nargs="?",
        help=f"file to {verb}; its content hash is the subject (omit if passing --digest)",
    )
    parser.add_argument(
        "--digest",
        help=f"{_DIGEST_PREFIX}<hex> to {verb} directly, when the bytes are not to hand",
    )


def add_sign_arguments(parser: argparse.ArgumentParser) -> None:
    """`sign` — detached ECDSA P-256 signature over a file's content hash."""
    _add_subject_arguments(parser, verb="sign")
    parser.add_argument(
        "--key",
        required=True,
        help=f"ECDSA private-key PEM to sign with (mint one with `{_KEYGEN}`)",
    )
    parser.add_argument("--out", help="write the signature here (default: stdout)")


def add_verify_arguments(parser: argparse.ArgumentParser) -> None:
    """`verify` — check a detached signature against a file and a trusted key."""
    _add_subject_arguments(parser, verb="verify")
    parser.add_argument("--signature", required=True, help="the detached signature `sign` produced")
    # Required, unlike `astro-mine hub verify --trusted-key`, and the asymmetry is deliberate.
    # Hub's check still means something without a key: it re-establishes the registry's own
    # integrity chain and the presence of every required attestation. This one would not. A
    # signature carries its signer's public key, so an attacker who alters the file can re-sign it
    # and pass -- "someone signed this" is not a result worth printing next to the word `ok`.
    parser.add_argument(
        "--key",
        required=True,
        help="public-key PEM the signer must match; required, because a signature carries its "
        "own key and verifying against that alone proves nothing about who made it",
    )


def add_provenance_arguments(parser: argparse.ArgumentParser) -> None:
    """`provenance` — an in-toto Statement carrying SLSA v1 provenance."""
    _add_subject_arguments(parser, verb="describe")
    parser.add_argument("--name", required=True, help="artifact name the provenance is about")
    parser.add_argument("--version", required=True, help="artifact version")
    parser.add_argument(
        "--builder-id",
        required=True,
        help="what produced the artifact; required, because it is a provenance claim Seal will "
        "not make on your behalf",
    )
    parser.add_argument(
        "--input",
        action="append",
        metavar="DIGEST",
        help=f"{_DIGEST_PREFIX}<hex> of a build input, recorded as a resolved dependency "
        f"(repeatable)",
    )
    parser.add_argument("--out", help="write the provenance here (default: stdout)")


def add_sbom_arguments(parser: argparse.ArgumentParser) -> None:
    """`sbom` — a CycloneDX bill of materials."""
    parser.add_argument("--name", required=True, help="artifact name the SBOM is about")
    parser.add_argument("--version", required=True, help="artifact version")
    parser.add_argument(
        "--component",
        action="append",
        metavar="NAME==VERSION",
        help="a component to list in the bill of materials (repeatable)",
    )
    parser.add_argument("--out", help="write the SBOM here (default: stdout)")


def add_inspect_arguments(parser: argparse.ArgumentParser) -> None:
    """`inspect` — identify and shape-check a signature, provenance or SBOM document."""
    parser.add_argument("document", help="a signature, SLSA provenance, or CycloneDX SBOM")


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        "Astro-Mine Seal — sign, verify and describe loose artifacts, offline. Anything addressed "
        f"by a registry reference belongs to `astro-mine hub`; mint a keypair with `{_KEYGEN}`."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sign = sub.add_parser("sign", help="sign a file or digest with an ECDSA P-256 key")
    add_sign_arguments(sign)
    sign.set_defaults(func=_cmd_sign)

    verify = sub.add_parser(
        "verify",
        help="verify a detached signature over a loose file (for a published artifact, "
        "use `astro-mine hub verify`)",
    )
    add_verify_arguments(verify)
    verify.set_defaults(func=_cmd_verify)

    provenance = sub.add_parser("provenance", help="emit SLSA v1 provenance for an artifact")
    add_provenance_arguments(provenance)
    provenance.set_defaults(func=_cmd_provenance)

    sbom = sub.add_parser("sbom", help="emit a CycloneDX SBOM for an artifact")
    add_sbom_arguments(sbom)
    sbom.set_defaults(func=_cmd_sbom)

    inspect = sub.add_parser(
        "inspect", help="identify an attestation document and check it is well-shaped"
    )
    add_inspect_arguments(inspect)
    inspect.set_defaults(func=_cmd_inspect)


class _Command:
    """`astro-mine seal <verb>` — sign, verify and describe artifacts."""

    name = "seal"
    help = "sign, verify and describe artifacts"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        _add_arguments(parser)

    def run(self, args: argparse.Namespace) -> int:
        # The backstop for the no-tracebacks-on-user-input rule, and the fail-closed boundary.
        # `SignatureError` is the whole point of the group: a tampered file, a signature for
        # another artifact, an untrusted signer and a malformed key all arrive here, and every one
        # of them must read as a refusal rather than a crash. Anything else still raises -- a real
        # defect must not be dressed up as bad input.
        try:
            return int(args.func(args))
        except (SignatureError, AttestationError) as exc:
            print(f"astro-mine seal {args.command}: verification failed: {exc}", file=sys.stderr)
            return 1
        except (InputError, OSError, ValueError) as exc:
            print(f"astro-mine seal {args.command}: {exc}", file=sys.stderr)
            return 1


command = _Command()
