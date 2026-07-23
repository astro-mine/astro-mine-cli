# astro-mine-cli

**The discoverable umbrella CLI for [Astro-Mine](https://github.com/astro-mine).**
One command — `astro-mine <verb>` — in front of a platform that ships a CLI per component, so a
user who does not yet know which package owns an action can guess the *action* and find it. Every
component CLI keeps working when invoked directly; the umbrella is the discoverable entry, **not**
a replacement.

> **Status — Phase 1.** The dispatcher ships: verbs are discovered from the `astro_mine.cli`
> entry-point group, loaded only when they run, and a missing component names its own install.
> **No component registers a verb yet** — those PRs land in each component's repo, tracked by
> [astro-mine/docs#57](https://github.com/astro-mine/docs/issues/57) — so on a normal install today
> `astro-mine` lists the platform and tells you what to install for each verb. Design authority:
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

With no components installed, the listing is still a map of the platform rather than an empty
shell — which is the point, since a newcomer meets this screen *before* installing anything:

```
Verbs:
  score     run a policy on a scenario and score it
  fetch     download a scenario's pinned content

Available from components that are not installed here:
  train     train a policy and export it [astro-mine-learn]
  run       run a scenario in the simulator [astro-mine-sim]
  ...

Every component CLI also works directly (`astro-mine-bench score`, `fleet validate`).
`astro-mine <verb> --help` shows a verb's own options.
```

Ask for a verb whose component is absent and you get the fix, not a shrug:

```console
$ astro-mine train
`astro-mine train` needs astro-mine-learn — install it with `pip install astro-mine-learn`
(or `uv add astro-mine-learn`), then re-run.
```

A missing component should say what is missing — never a traceback, never a bare "unknown
command" (RFC-0011 §4). A verb nobody advertises *is* an unknown command, and says so, listing
what is available.

## How a component contributes a verb — no PR to this repo

A component (or a third party) contributes a subcommand by declaring an entry point in **its own**
`pyproject.toml`:

```toml
[project.entry-points."astro_mine.cli"]
train = "astro_mine.learn.cli:umbrella"
```

The target is an object with four members — `name`, `help`, `add_arguments(parser)`, and
`run(args) -> int`. It is a **structural** contract: nothing to import, nothing to subclass, so a
component never takes a dependency on the umbrella to be reachable from it.

No component imports the umbrella, and the umbrella imports no component to *list* it. This is the
extension mechanism the platform already uses everywhere else — `astro_mine.providers`,
`astro_mine.field_models`, `astro_mine.mind.tier_plugins`, `astro_mine.bench.runners`,
`astro_mine.allocate.solvers` — and the CLI is not special enough to invent a different one.

Two adapter styles work, and a component can start with the cheap one:

- **passthrough** — forward the tail to the `main(argv)` the component already has
  (`astro-mine studio serve`); nothing is re-declared, so the umbrella's help cannot drift from the
  component's real flags;
- **per-verb** — declare the verb's own arguments, for an action worth promoting to the top level
  (`astro-mine score`).

Worked examples of both live in [`tests/fixtures/provider`](tests/fixtures/provider), which is a
real distribution installed by the test suite — so they are copyable, and they are known to work.

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
  _protocol.py             # the contribution contract
  _manifest.py             # the static first-party table (verb -> distribution, help)
  _discovery.py            # entry-point enumeration; the only place a provider is imported
  _dispatch.py             # the two-phase parser and the dispatch loop
tests/                     # mirrors the package layout
  fixtures/provider/       # a third-party distribution, installed by the integration lane
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
