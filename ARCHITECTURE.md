# Architecture — astro-mine-cli

The module map and the decisions behind it. The design authority is
**[RFC-0011](https://github.com/astro-mine/docs/blob/main/rfc/0011-umbrella-cli.md)** (accepted);
this document summarizes what it settled and records what implementation decided on top. The
platform-wide view is [`architecture/system.md §4`](https://github.com/astro-mine/docs/blob/main/architecture/system.md),
where `astro-mine-cli` sits in the Backbone row.

## What this package is

A **thin dispatcher**: discovery, routing, and packaging. It owns no schema, no message, no wire
type, and it makes **no change to Core** (`CORE_INTERFACE_VERSIONS` stays `0.1.0`). Its entire job
is to let a user guess an *action* — `astro-mine score` — and reach the component that implements
it.

## The shape, and why it is this one

RFC-0011 §1 chose an **entry-point group plus a static first-party manifest**, over three
alternatives. The two halves solve different problems and neither is redundant:

| Mechanism | Solves |
|---|---|
| **(a) Discovery** — enumerate `astro_mine.cli` via `importlib.metadata` | A component contributes a verb by declaring an entry point, with **no PR to this package**. Enumeration reads distribution metadata and imports nothing. |
| **(b) The first-party manifest** — plain strings, verb → distribution | Pure discovery cannot name a fix for an **uninstalled** component: with no `astro-mine-learn` there is no `train` entry point, and the umbrella could only say "unknown command". The manifest is what turns that into *"`astro-mine train` needs `astro-mine-learn` — `pip install astro-mine-learn`"*. |

The manifest governs **only** that friendly hint. Third-party verbs are discovered dynamically and
need no entry in it, so it does not reintroduce a PR-to-extend chokepoint through the back door.

## The four constraints, and where each is enforced

| Constraint | Enforced by |
|---|---|
| **Zero runtime dependencies** (CX-LOCAL — the deciding constraint) | `pyproject.toml` `dependencies = []`; `tests/test_packaging.py::test_declares_no_runtime_dependencies`; the bare-venv install step in CI |
| **No PR to extend** | Discovery keys on the group *name*; a fixture provider in the test suite proves a third party can register (#2) |
| **Degrade honestly** | The first-party manifest + the empty-state epilog; never a traceback (#2) |
| **Additive** | Component CLIs are untouched and keep working when invoked directly |

### Why there is no `CORE_REPO_TOKEN` step in CI

Every sibling repo's CI rewrites GitHub HTTPS fetches with a PAT so `uv sync` can resolve the
private `astro-mine-core` git source. This repo has no such step **because it has nothing private
to resolve** — the dependency list is empty. The absence is deliberate and load-bearing: if that
step ever becomes necessary here, the zero-dependency rule has already been broken upstream of it.
The workflow says so at the point where a copy-paste from a sibling would land.

## Module map

```
src/astro_mine/cli/
  __init__.py    # public surface: __version__, build_parser, main
  _app.py        # the top-level parser and the process entry point
```

`__init__` stays a re-export list so the argparse wiring has somewhere to grow. The console script
`astro-mine` resolves to `astro_mine.cli:main`; that name and target are pinned by a test, because
RFC-0011's per-component dispatch (`astro-mine studio serve`) is a thin call into an already-shipped
subcommand and only works if they stay put.

### Why `build_parser()` is a function, not a module-level constant

The verb set is read from installed metadata **at build time**, so a cached parser would freeze the
environment as it looked at first import. Building per invocation also lets the tests construct a
parser against a fixture environment without reimporting the module.

## Decisions

### Settled here

- **`Development Status :: 3 - Alpha` from the first commit.** The package ships a working console
  script; `1 - Planning` is platform-wide drift
  ([astro-mine/docs#40](https://github.com/astro-mine/docs/issues/40)), not a status to inherit.
- **The empty state exits 0.** A bare `astro-mine` with no verbs registered prints help and
  succeeds — the user asked a dispatcher what it can do, and "nothing yet, and here is what to run
  instead" is a complete answer. An *unrecognized* verb still fails (exit 2); silence there would
  be the dishonest case.
- **No git tags yet**, so `hatch-vcs` stamps a development version. This matches the sibling repos,
  which are also untagged during private incubation; the version is *derived*, so it cannot drift
  from the source of truth.

### Deferred to [#2](https://github.com/astro-mine/astro-mine-cli/issues/2)

- **The `Subcommand` protocol's exact shape** — RFC-0011 explicitly leaves this to implementation.
  It MUST be a **structural `typing.Protocol`, not a base class**: a component forced to
  `from astro_mine.cli import Subcommand` would make the umbrella a dependency of every component,
  inverting the layering this package exists to protect (`conventions.md §1.1`).
- **Whether `astro-mine` re-exposes a component's full subcommand tree**, or only the verbs the
  component registers. Recommendation on file: only what is registered — the component owns its
  surface, the umbrella owns routing.
- **Shell completion** over the discovered verb set.

### Owned elsewhere

- **The naming rule and the alias/deprecation policy** are normative in
  [`conventions.md §13`](https://github.com/astro-mine/docs/blob/main/architecture/conventions.md),
  not here. The renames themselves (`fleet`/`worlds`/`link`/`prospect`, `astro-mine-train`) land in
  each component's own repo, tracked by
  [astro-mine/docs#57](https://github.com/astro-mine/docs/issues/57).
- **`validate` federation** (RFC §6): the format's owner owns its validator, Core owns `$id`-keyed
  dispatch for Core formats, and the umbrella only routes. No checker is reimplemented here.
- **The umbrella's release cadence** relative to components —
  [`VERSIONING.md`](https://github.com/astro-mine/docs/blob/main/VERSIONING.md).
