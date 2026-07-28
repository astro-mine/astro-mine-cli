"""Packaging invariants — the rules that make this package what astro-mine-cli#12 decided it is.

Not smoke tests. Each of these encodes a decision that a convenient edit would quietly undo,
and a rule enforced only by review is a rule that erodes on the first convenient import.
"""

from __future__ import annotations

from importlib.metadata import entry_points, requires

import astro_mine.cli

DISTRIBUTION = "astro-mine-cli"


def test_depends_only_on_the_platform() -> None:
    """Exactly one runtime dependency, and it is `astro-mine-platform`.

    This package used to declare none at all, and that emptiness was asserted here for the same
    reason this is: RFC-0011 §1 built the umbrella as a zero-dependency dispatcher so installing
    it for one verb could not drag Ray, CP-SAT, SPICE and a Rust toolchain onto the machine.

    Consolidation dissolved that premise -- the platform is one wheel already carrying all of
    it -- so the dependency is now correct. What must not happen is a *second* one. Every
    command here is a thin wrapper over a platform function; anything a command needs that the
    platform does not export is a platform change, not a new dependency in this file.
    """
    declared = {r.split()[0].split(";")[0].strip() for r in (requires(DISTRIBUTION) or [])}
    assert declared == {"astro-mine-platform"}, (
        f"expected exactly one runtime dependency, found {sorted(declared)}. Adding one is a "
        f"design change -- take it through the RFC."
    )


def test_astro_mine_is_the_one_console_script() -> None:
    """One executable on PATH, from this package, and none from the platform.

    The headline acceptance criterion. Before this change a single `pip install` put twenty
    executables on PATH: `astro-mine`, fifteen `astro-mine-*` binaries, and four bare aliases
    (`fleet`, `link`, `prospect`, `worlds`) that squatted names no library should own.
    """
    scripts = {ep.name: ep.value for ep in entry_points(group="console_scripts")}
    assert scripts.get("astro-mine") == "astro_mine.cli:main"

    ours = {n for n in scripts if n == "astro-mine" or n.startswith("astro-mine-")}
    assert ours == {"astro-mine"}, f"the platform still ships console scripts: {sorted(ours)}"
    for squatted in ("fleet", "link", "prospect", "worlds"):
        assert squatted not in scripts, f"the deprecated bare alias {squatted!r} is still declared"


def test_the_platform_declares_no_cli_entry_points() -> None:
    """The four `astro_mine.cli*` groups are this package's to fill, not the platform's.

    They remain live groups -- a third party still extends the CLI by registering into them --
    but the platform registering into them is what produced the collision this change removes:
    its `fleet`/`guard`/`worlds`/... entries shadowed the component names at the top level.
    """
    for group in (
        "astro_mine.cli",
        "astro_mine.cli.validators",
        "astro_mine.cli.scaffolds",
        "astro_mine.cli.plugin_scaffolds",
    ):
        providers = {
            ep.dist.name for ep in entry_points(group=group) if ep.dist is not None
        }
        assert "astro-mine-platform" not in providers, (
            f"astro-mine-platform still registers into {group}"
        )


def test_version_is_resolved_from_installed_metadata() -> None:
    """``__version__`` is derived (hatch-vcs), not a hardcoded string that can drift."""
    assert astro_mine.cli.__version__
    assert astro_mine.cli.__version__ != "0.0.0.dev0", (
        "the fallback fired, so the package under test is not installed; run `uv sync`"
    )
