"""Print the platform dependency exactly as ``pyproject.toml`` declares it.

CI installs the built wheel into an environment holding nothing else, to check the claim this
package makes about itself. ``uv pip install dist/*.whl`` cannot resolve ``astro-mine-platform``
on its own -- ``uv pip`` does not read ``[tool.uv.sources]``, since that is project configuration
and a built wheel's metadata has nowhere to put a git URL -- so the platform is installed first,
from the very pin ``pyproject.toml`` declares.

**That reading lived inline in the workflow as a one-liner, and it broke.** It hard-coded the
``rev`` key; astro-mine-cli#36 replaced ``rev`` with ``branch = "main"`` (conventions.md §3.1: this
build MUST run against the platform at HEAD, not a released pin) and the workflow was not moved
with it, so the last step of every run died on ``KeyError: 'rev'``. Nobody saw it, because the org
was out of Actions minutes and then the test lane failed first.

So the reading lives here instead: one implementation, called by the workflow *and* by
``tests/test_packaging.py``, which is what makes the pin and the thing that installs it unable to
drift apart again. Run it by hand to see what CI will install::

    python scripts/platform_pin.py
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

#: The git ref keys uv accepts on a source, most specific first. `rev` pins a commit, `tag` a
#: release, `branch` a moving head; uv permits exactly one, and §3.1 requires `branch` here.
REF_KEYS: tuple[str, ...] = ("rev", "tag", "branch")

DISTRIBUTION = "astro-mine-platform"


def platform_requirement(pyproject: Path) -> str:
    """The PEP 508 requirement string that installs the declared platform pin."""
    data: dict[str, Any] = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    try:
        source = data["tool"]["uv"]["sources"][DISTRIBUTION]
    except KeyError:  # pragma: no cover - a missing source is a broken pyproject, not a pin change
        raise SystemExit(f"{pyproject}: no [tool.uv.sources] entry for {DISTRIBUTION}") from None

    url = source.get("git")
    if not url:
        raise SystemExit(
            f"{pyproject}: {DISTRIBUTION} is not a git source; nothing to install from"
        )

    for key in REF_KEYS:
        if key in source:
            return f"{DISTRIBUTION} @ git+{url}@{source[key]}"

    raise SystemExit(
        f"{pyproject}: {DISTRIBUTION} declares none of {REF_KEYS}, so there is no ref to install. "
        "If the pin's shape changed, this script is what CI reads -- change it here."
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    print(platform_requirement(root / "pyproject.toml"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
