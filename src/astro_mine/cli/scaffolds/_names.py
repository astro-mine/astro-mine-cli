"""One name rule, shared by every plugin scaffold.

An entry-point name is matched **literally** by `importlib.metadata`, so a name that is not a
usable identifier produces a package that installs, registers nothing resolvable, and fails at
lookup — after publication, when the name is already in somebody's lockfile.

Four of the eight scaffolds had no check at all and two had their own copy of the regex
(astro-mine-cli#14). This is the one implementation: the rule lives here, the message names the
flag the user actually typed, and adding a ninth kind inherits it.

Kinds whose flag is a closed set (`--tier`, `--kind` on `provider`) do not call this — argparse
`choices=` refuses a bad value before any handler runs, which is strictly better and free.
"""

from __future__ import annotations

import keyword
import re

__all__ = ["check_module", "check_plugin_name", "check_reserved_verb"]

#: Lower-case, digit- or letter-initial, then letters/digits/underscore/hyphen/dot.
#:
#: **Dots are allowed on purpose.** The platform's own ids are dotted -- `mind.control.mpc`,
#: `marl.demo.algorithm`, `guard.shield` -- and entry-point names permit them. A rule that
#: rejected dots would refuse the scaffolds' own defaults, which is how this was caught.
_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]*")


def check_plugin_name(value: str, *, command: str, flag: str, noun: str) -> str | None:
    """``None`` if ``value`` is a usable entry-point name, else the message to print."""
    if _NAME.fullmatch(value):
        return None
    return (
        f"astro-mine plugin new {command}: {value!r} is not a usable {noun}; it becomes an "
        f"entry-point name, which is matched literally, so a package registering it could never "
        f"be resolved. Use lower-case letters, digits, '_', '-' or '.'. "
        f"Pass {flag} explicitly."
    )


def check_module(value: str, *, command: str) -> str | None:
    """``None`` if ``value`` can be an import path, else the message to print.

    The emitted package has to be importable: `--module 9lives` and `--module class` both
    produce a tree that cannot be loaded, and the failure surfaces as a SyntaxError or a bare
    ImportError far from the flag that caused it.
    """
    if value.isidentifier() and not keyword.iskeyword(value):
        return None
    reason = "a Python keyword" if keyword.iskeyword(value) else "not a Python identifier"
    return (
        f"astro-mine plugin new {command}: {value!r} is {reason}, so the package it names could "
        f"not be imported. Pass --module explicitly."
    )


def check_reserved_verb(value: str) -> str | None:
    """``None`` unless ``value`` is a top-level name this CLI already owns.

    `astro-mine plugin new cli --verb validate` used to emit a package claiming a router the
    CLI provides. `astro_mine.cli._dispatch` catches the collision at dispatch and exits 2
    naming both claimants — correct, but far too late: the author only sees it once the package
    is installed somewhere. Catching it here costs one set lookup at authoring time.
    """
    from astro_mine.cli._registry import COMPONENTS

    reserved = {*COMPONENTS, "validate", "new", "plugin"}
    if value not in reserved:
        return None
    kind = "component" if value in COMPONENTS else "router"
    return (
        f"astro-mine plugin new cli: {value!r} is a {kind} this CLI already provides, so a "
        f"package claiming it would be refused at dispatch as a collision. Choose another verb; "
        f"`astro-mine --help` lists the names that are taken."
    )
