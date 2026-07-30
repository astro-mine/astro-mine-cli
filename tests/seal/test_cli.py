"""`astro-mine seal <verb>` — the shell surface over the platform's artifact-integrity component.

Seal was the archetypal command-line tool with no command line (astro-mine-cli#17). These tests
are written around the two properties that make the group worth having rather than around its
line count:

**The round trip closes, and only for the right bytes.** A file signed by `sign` verifies with
`verify`; the same file altered by one byte does not, and neither does the same file verified
against a different key. Those two negatives are the feature — a signature check that cannot fail
is decoration.

**Nothing fails with a traceback.** Every refusal here is a user-input condition or a verification
failure, and both are answers, not crashes. A traceback tells a user their *input* was wrong by
making it look like the *tool* broke.

Offline throughout: Seal's signer is keyed ECDSA P-256 with no Fulcio, Rekor or OIDC, so none of
this needs a network, an account, or a registry (CX-LOCAL).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from astro_mine.seal import generate_keypair

from astro_mine.cli import main as _astro_mine


def main(argv: list[str] | None = None) -> int:
    """`astro-mine seal <verb>` — the one address these commands have."""
    return _astro_mine(["seal", *(argv or [])])


@pytest.fixture
def keys(tmp_path: Path) -> tuple[str, str]:
    """A cosign keypair on disk, as `astro-mine hub keygen` would leave it."""
    private_pem, public_pem = generate_keypair()
    (tmp_path / "cosign.key").write_bytes(private_pem)
    (tmp_path / "cosign.pub").write_bytes(public_pem)
    return str(tmp_path / "cosign.key"), str(tmp_path / "cosign.pub")


@pytest.fixture
def artifact(tmp_path: Path) -> str:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"a lunar polar ice map\n")
    return str(path)


def _signed(artifact: str, key: str, tmp_path: Path) -> str:
    signature = str(tmp_path / "artifact.sig")
    assert main(["sign", artifact, "--key", key, "--out", signature]) == 0
    return signature


# --- the round trip -------------------------------------------------------------------------------


def test_a_signed_file_verifies(
    artifact: str, keys: tuple[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The acceptance criterion: sign, then verify, offline, with no registry."""
    private, public = keys
    signature = _signed(artifact, private, tmp_path)
    capsys.readouterr()

    assert main(["verify", artifact, "--signature", signature, "--key", public]) == 0
    assert capsys.readouterr().out.startswith("ok sha256:")


def test_a_tampered_file_fails_with_a_message_not_a_traceback(
    artifact: str, keys: tuple[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One byte changed and the signature no longer covers the file — the whole point."""
    private, public = keys
    signature = _signed(artifact, private, tmp_path)
    Path(artifact).write_bytes(b"a lunar polar ice map (edited)\n")
    capsys.readouterr()

    assert main(["verify", artifact, "--signature", signature, "--key", public]) == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "verification failed" in err


def test_a_signature_from_another_key_is_refused(
    artifact: str, keys: tuple[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Pinned trust, and the reason `--key` is required.

    A signature carries its signer's public key, so an attacker who alters a file can simply
    re-sign it. Without a key to pin against, `verify` would answer "somebody signed this" — a
    result no reader distinguishes from "verified".
    """
    private, _ = keys
    signature = _signed(artifact, private, tmp_path)
    _, stranger_pem = generate_keypair()
    stranger = tmp_path / "stranger.pub"
    stranger.write_bytes(stranger_pem)
    capsys.readouterr()

    assert main(["verify", artifact, "--signature", signature, "--key", str(stranger)]) == 1
    assert "not the trusted key" in capsys.readouterr().err


def test_verify_requires_a_key(
    artifact: str, keys: tuple[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not optional, unlike `astro-mine hub verify --trusted-key`. See the test above for why."""
    private, _ = keys
    signature = _signed(artifact, private, tmp_path)
    with pytest.raises(SystemExit) as caught:
        main(["verify", artifact, "--signature", signature])
    assert caught.value.code == 2


def test_a_digest_can_be_signed_without_the_bytes(
    keys: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """`--digest` covers the case where you have the content address but not the content."""
    private, _ = keys
    digest = "sha256:" + "b" * 64
    assert main(["sign", "--digest", digest, "--key", private]) == 0
    signature = json.loads(capsys.readouterr().out)
    assert signature["payload"] == digest


def test_a_signature_is_written_to_stdout_by_default(
    artifact: str, keys: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """So it pipes. `--out` is for when you want it on disk under a name."""
    private, _ = keys
    assert main(["sign", artifact, "--key", private]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["scheme"] == "sigstore_cosign"


# --- what a subject may be ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        pytest.param([], "pass a file to hash", id="neither"),
        pytest.param(["ARTIFACT", "--digest", "sha256:" + "c" * 64], "not both", id="both"),
        pytest.param(["--digest", "nonsense"], "not a content address", id="malformed"),
        pytest.param(["--digest", "sha256:"], "not a content address", id="empty-hex"),
    ],
)
def test_the_subject_is_exactly_one_thing(
    argv: list[str],
    expected: str,
    artifact: str,
    keys: tuple[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A file *or* a digest, never both and never neither, and a digest that is really one.

    The malformed case is the one that matters: `sign_digest` will sign any string, so a typo'd
    `--digest` produces a perfectly valid signature over the wrong subject — a failure the user is
    least equipped to notice later.
    """
    private, _ = keys
    resolved = [artifact if token == "ARTIFACT" else token for token in argv]
    assert main(["sign", *resolved, "--key", private]) == 1
    assert expected in capsys.readouterr().err


def test_an_unreadable_file_is_named(
    tmp_path: Path, keys: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    private, _ = keys
    missing = str(tmp_path / "gone.bin")
    assert main(["sign", missing, "--key", private]) == 1
    err = capsys.readouterr().err
    assert missing in err and "Traceback" not in err


def test_an_unreadable_key_is_named(
    artifact: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["sign", artifact, "--key", str(tmp_path / "absent.key")]) == 1
    assert "signing key" in capsys.readouterr().err


def test_a_malformed_key_fails_closed(
    artifact: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Seal raises `SignatureError`; the group turns it into a refusal, not a crash."""
    key = tmp_path / "not.key"
    key.write_bytes(b"-----BEGIN PRIVATE KEY-----\nnope\n-----END PRIVATE KEY-----\n")
    assert main(["sign", artifact, "--key", str(key)]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_an_unwritable_out_path_is_reported(
    artifact: str, keys: tuple[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private, _ = keys
    out = tmp_path / "no-such-dir" / "sig.json"
    assert main(["sign", artifact, "--key", private, "--out", str(out)]) == 1
    assert "cannot write" in capsys.readouterr().err


# --- the documents `hub publish` attaches ---------------------------------------------------------


def test_provenance_binds_the_subject_to_its_builder(
    artifact: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """SLSA v1, deterministic and offline: no clock, so the same build reproduces the bytes."""
    argv = [
        "provenance",
        artifact,
        "--name",
        "ice-map",
        "--version",
        "1.0.0",
        "--builder-id",
        "did:web:example.org/ci",
        "--input",
        "sha256:" + "d" * 64,
    ]
    assert main(argv) == 0
    first = capsys.readouterr().out
    document = json.loads(first)
    assert document["predicateType"] == "https://slsa.dev/provenance/v1"
    assert document["subject"][0]["name"] == "ice-map:1.0.0"
    assert document["predicate"]["runDetails"]["builder"]["id"] == "did:web:example.org/ci"
    assert document["predicate"]["buildDefinition"]["resolvedDependencies"]

    assert main(argv) == 0
    assert capsys.readouterr().out == first, "provenance must be byte-reproducible"


def test_a_malformed_input_digest_is_refused(
    artifact: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--input` is checked with the same rule as `--digest`; a bad one is not recorded."""
    assert (
        main(
            [
                "provenance",
                artifact,
                "--name",
                "n",
                "--version",
                "1",
                "--builder-id",
                "b",
                "--input",
                "sha512:abc",
            ]
        )
        == 1
    )
    assert "not a content address" in capsys.readouterr().err


def test_sbom_lists_the_components_it_was_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "sbom.json"
    argv = [
        "sbom",
        "--name",
        "ice-map",
        "--version",
        "1.0.0",
        "--component",
        "numpy==2.1.0",
        "--component",
        "rasterio==1.3.9",
        "--out",
        str(out),
    ]
    assert main(argv) == 0
    assert "wrote SBOM" in capsys.readouterr().out

    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["bomFormat"] == "CycloneDX"
    assert [c["name"] for c in document["components"]] == ["numpy", "rasterio"]


def test_an_sbom_needs_no_components(capsys: pytest.CaptureFixture[str]) -> None:
    """An empty bill of materials is a legitimate claim: "this artifact has no dependencies"."""
    assert main(["sbom", "--name", "n", "--version", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["components"] == []


@pytest.mark.parametrize("value", ["numpy", "numpy==", "==2.1.0", ""])
def test_a_component_must_be_name_and_version(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """`name==version`, so a version containing `=` stays unambiguous."""
    assert main(["sbom", "--name", "n", "--version", "1", "--component", value]) == 1
    assert "is not `name==version`" in capsys.readouterr().err


# --- reading evidence you were handed -------------------------------------------------------------


def test_inspect_identifies_each_document_kind(
    artifact: str, keys: tuple[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One reader for the three payloads `astro-mine hub publish` attaches."""
    private, _ = keys
    signature = _signed(artifact, private, tmp_path)
    provenance = tmp_path / "prov.json"
    sbom = tmp_path / "sbom.json"
    assert (
        main(
            [
                "provenance",
                artifact,
                "--name",
                "n",
                "--version",
                "1",
                "--builder-id",
                "b",
                "--out",
                str(provenance),
            ]
        )
        == 0
    )
    assert main(["sbom", "--name", "n", "--version", "1", "--out", str(sbom)]) == 0
    capsys.readouterr()

    for path, expected in (
        (signature, "signature\tscheme=sigstore_cosign"),
        (str(provenance), "SLSA provenance\tsubject=n:1"),
        (str(sbom), "SBOM\tsubject=n@1"),
    ):
        assert main(["inspect", path]) == 0
        assert capsys.readouterr().out.startswith(expected)


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        pytest.param({"hello": "world"}, "is not a signature", id="unrecognized"),
        pytest.param({"predicateType": "https://example.org/v1"}, "SLSA", id="wrong-predicate"),
        pytest.param({"bomFormat": "SPDX"}, "SBOM", id="wrong-bom-format"),
        pytest.param({"scheme": "not-a-scheme"}, "Signature", id="bad-signature"),
    ],
)
def test_inspect_refuses_rather_than_guesses(
    document: dict[str, object],
    expected: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A document nobody claims is an error, exactly as `astro-mine validate` treats one.

    Shape-checking is fail-closed too: a statement with the wrong `predicateType` is not SLSA
    provenance, and calling it provenance because it has the field would be the permissive
    default Seal does not have.
    """
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert main(["inspect", str(path)]) == 1
    assert expected in capsys.readouterr().err


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param("{not json", "not valid JSON", id="unparseable"),
        pytest.param('["a", "list"]', "not a JSON object", id="not-an-object"),
    ],
)
def test_a_document_that_is_not_a_json_object_is_refused(
    content: str, expected: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "doc.json"
    path.write_text(content, encoding="utf-8")
    assert main(["inspect", str(path)]) == 1
    assert expected in capsys.readouterr().err


def test_verify_refuses_a_document_that_is_not_a_signature(
    artifact: str, keys: tuple[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--signature` pointed at the wrong file is a common slip, and it reads as one."""
    _, public = keys
    not_a_signature = tmp_path / "sbom.json"
    assert main(["sbom", "--name", "n", "--version", "1", "--out", str(not_a_signature)]) == 0
    capsys.readouterr()

    assert main(["verify", artifact, "--signature", str(not_a_signature), "--key", public]) == 1
    assert "is not a Signature document" in capsys.readouterr().err


# --- the group's place in the platform ------------------------------------------------------------


def test_seal_is_listed_at_the_top_level(capsys: pytest.CaptureFixture[str]) -> None:
    """`astro-mine --help` must offer it, or nobody finds it (astro-mine-cli#17)."""
    assert _astro_mine([]) == 0
    assert "seal" in capsys.readouterr().out


def test_seal_points_at_the_one_keygen(capsys: pytest.CaptureFixture[str]) -> None:
    """No `seal keygen`: exactly one documented way to mint a key, and it is Hub's.

    Asserted on the description rather than left to review, because a second keygen is precisely
    the kind of convenience that gets added without noticing the first one exists.
    """
    with pytest.raises(SystemExit):
        _astro_mine(["seal", "--help"])
    out = capsys.readouterr().out
    assert "astro-mine hub keygen" in out
    assert "keygen" not in out.split("positional arguments")[1].split("options:")[0].replace(
        "astro-mine hub keygen", ""
    )


def test_seal_verify_says_which_verify_it_is_not(capsys: pytest.CaptureFixture[str]) -> None:
    """The collision astro-mine-cli#17 asked to resolve, resolved in the help text.

    `astro-mine hub verify` checks a published artifact's whole supply chain against a registry;
    this checks one detached signature over one loose file. Both stand, and each says so.
    """
    with pytest.raises(SystemExit):
        _astro_mine(["seal", "--help"])
    assert "astro-mine hub verify" in capsys.readouterr().out
