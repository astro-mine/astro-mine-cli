# astro-mine-cli

**The discoverable umbrella CLI for [Astro-Mine](https://github.com/astro-mine).**
One command — `astro-mine <verb>` — in front of a platform that ships a CLI per component, so a
user who does not yet know which package owns an action can guess the *action* and find it. Every
component CLI keeps working when invoked directly; the umbrella is the discoverable entry, **not**
a replacement.

> **Status — Phase 1, standup.** This release is the shell: packaging, the `astro-mine` console
> script, the CI lane, and a parser that runs and truthfully reports it has nothing to dispatch to.
> **Verb discovery lands in [#2](https://github.com/astro-mine/astro-mine-cli/issues/2)** — until
> then, run the component CLIs directly. Design authority:
> **[RFC-0011](https://github.com/astro-mine/docs/blob/main/rfc/0011-umbrella-cli.md)** (accepted).

## The one rule this package exists to hold

**It has no runtime dependencies. Not one — not even `astro-mine-core`.**

RFC-0011 weighed an umbrella that depends on every component and rejected it: installing it to get
`astro-mine score` would drag Ray, a Rust toolchain, CP-SAT and SPICE onto the machine, and the
local tier that *must always work* (`conventions.md §7`) would become the heaviest install on the
platform.

So the umbrella depends on an entry-point **group name**, `astro_mine.cli`, and never on a provider.
It reads installed distribution metadata to build its help, and imports a component **only when
that component's verb actually runs**. A machine with one component installed pays for one.

This is enforced, not asserted: `tests/test_packaging.py` fails if the distribution ever declares a
runtime dependency, and CI installs the built wheel into an empty virtualenv and runs it there.

## Quickstart

```bash
conda create -n astro-mine-cli python=3.12 && conda activate astro-mine-cli
uv sync
uv run astro-mine --help
```

With no components installed you get the honest empty state:

```
usage: astro-mine [-h] [--version]

The Astro-Mine umbrella CLI — one front door to the platform's component CLIs.

No verbs are registered in this environment yet.
...
```

That is the correct output for a dispatcher with nothing to dispatch to — a missing component
should say what is missing, never traceback and never pretend (RFC-0011 §4).

## How a component contributes a verb — no PR to this repo

Once [#2](https://github.com/astro-mine/astro-mine-cli/issues/2) lands, a component (or a third
party) contributes a subcommand by declaring an entry point in **its own** `pyproject.toml`:

```toml
[project.entry-points."astro_mine.cli"]
train = "astro_mine.learn.cli:umbrella"
```

No component imports the umbrella, and the umbrella imports no component to list it. This is the
extension mechanism the platform already uses everywhere else — `astro_mine.providers`,
`astro_mine.field_models`, `astro_mine.mind.tier_plugins`, `astro_mine.bench.runners`,
`astro_mine.allocate.solvers` — and the CLI is not special enough to invent a different one.

## Command naming

`conventions.md §13` is normative:

- a component's **direct console script is `astro-mine-<package>`** — the prefix is uniform, and
  names the command after its package;
- the **umbrella surface is `astro-mine <verb>`** — verb-first, because the user is guessing the
  action; component-scoped actions read as `astro-mine <component> <verb>`.

Legacy bare names (`fleet`, `worlds`, `link`, `prospect`) and the mis-nouned `astro-mine-train` are
kept as aliases for one deprecation cycle and removed at the public-flip gate. New CLIs are born
prefixed — the alias surface only ever shrinks.

## Layout

```
src/astro_mine/cli/        # import path: astro_mine.cli
  _app.py                  # the top-level parser + `main`
tests/                     # mirrors the package layout
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the dispatcher's design and the decisions behind it.

## Development

Targets **Python 3.12** with a per-repo **conda** env and **uv**.

```bash
uv sync && uv run pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

Apache-2.0 — see [LICENSE](LICENSE). Copyright Astro-Mine project contributors.
