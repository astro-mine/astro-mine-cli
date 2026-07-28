# Architecture

`astro-mine-cli` is the platform's only command line. It depends on `astro-mine-platform` and
exposes one executable, `astro-mine`, under one grammar: `astro-mine <component> <verb>`.

## Why the CLI is a separate distribution

It would be simpler to ship the commands inside the platform wheel. Two reasons not to:

**The platform stops having a user interface.** Argparse trees, help strings, output formatting
and exit-code policy are a different concern from resource fields and rigid-body physics. With
them gone, the platform's only boundary is its library API, and "is this exported?" has a real
answer — the export audit for this change found exactly one function that was reachable only
through a command handler.

**One home for CLI decisions.** Help text, argument naming, exit-code conventions and `--json`
output shape are cross-cutting. They used to be decided thirteen times independently, which is
how the platform ended up with three addressing rules and seven subcommands that could not be
typed at all.

## Why it is no longer a zero-dependency dispatcher

RFC-0011 §1 built this package with **no** runtime dependencies — not even Core — and federated
first-party verbs through the `astro_mine.cli` entry-point group. Its "Alternatives considered"
(a) explicitly rejected *"one umbrella package depending on all components"* as violating
CX-LOCAL: `pip install` for one verb would drag Ray, CP-SAT, SPICE and a Rust toolchain onto
the machine.

Consolidation dissolved that premise. `astro-mine-platform` is **one wheel** already carrying
all of it, so there is no install this dependency makes heavier — the cost §1 refused to pay is
now paid by the platform simply existing. Meanwhile the indirection it bought decoupled
nothing: every component is always present, so first-party federation was a metadata round-trip
that hid which function ran.

What §1a actually protected is kept, by a mechanism that still works.

## Laziness: you pay for the command you ran

`astro-mine --help` imports **no** component. The listing comes from `_registry.py` — static
strings, no imports — and the dispatcher imports exactly one module, the one the user named.

That is what the two-phase parse is for. Phase one parses only *which* component; everything
after it is `argparse.REMAINDER`. Phase two imports that component's module and lets it parse
its own tail. A single-phase parser would have to call every component's `add_arguments` to
build the tree, importing all thirteen to render a help screen.

The cost is that top-level `--help` cannot show a component's own verbs. That is the trade, and
`astro-mine <component> --help` is where the real help lives.

## Layout

```
src/astro_mine/cli/
├── _dispatch.py      the root parser: 13 components + 3 routers
├── _registry.py      the static tables — plain strings, imports nothing
├── _protocol.py      the four-member contract a third-party verb satisfies
├── _discovery.py     third-party verb discovery (entry points)
├── _validators.py    validator federation: 4 built-in + third-party
├── _scaffolds.py     scaffold federation: 11 built-in + third-party
├── _validate.py      the `validate` router
├── _new.py           the `new` and `plugin new` routers
├── <component>/      one per component: core, fleet, worlds, link, prospect,
│                       sim, bench, learn, mind, guard, hub, cloud, studio
└── scaffolds/        the 12 kinds, grouped by owning component
```

## Two sources, one shape

First-party commands are dispatched **statically** from `_registry.py`. Third-party ones come
from the entry-point groups, because that is the no-PR-to-extend guarantee (RFC-0011 §3) and it
is unaffected by consolidation. Both are wrapped so the dispatcher cannot tell them apart.

Four groups stay live for third parties: `astro_mine.cli`, `astro_mine.cli.validators`,
`astro_mine.cli.scaffolds`, `astro_mine.cli.plugin_scaffolds`. The platform no longer registers
into any of them — its entries used to shadow the component names at the top level.

## The thin-wrapper rule

A module here MAY declare argparse arguments, read a `Namespace`, call a platform function,
format output, and map a result to an exit status.

It MUST NOT implement domain logic, define a schema or data model, hold state between
invocations, or import a platform private (`_`-prefixed) name.

Anything a command needs that the platform does not export is a platform change. This is not
style: `astro-mine fleet package` and Fleet's own packaging manifest must produce byte-identical
canonical JSON, and they only do that by calling the same exported function.

## Parser parity

`tests/fixtures/parser-snapshot.json` records all 50 verbs and 189 arguments as the platform's
own binaries declared them, captured before any code moved. `tests/test_parser_parity.py`
asserts the current parsers still match — option strings, defaults, `nargs`, `choices`,
`required`, help text.

Regenerating that fixture to make a test pass is not a fix. The fixture *is* the old behaviour,
and the old behaviour is the requirement; a verb that genuinely must change is a separate change
with its own justification, and the fixture moves in that commit.

## What is deliberately not here

Two entry points are not exposed as verbs, because neither is typed by a person and both are
invoked as `python -m` by machinery that depends on them: Bench's `eval-worker` (Cloud fans it
out per seed) and Sim's container ENTRYPOINT rewrite. They stay in the platform, where their
callers already look for them.

`astro-mine studio serve` reaches a command that cannot run in this distribution: the Studio
REST surface was deliberately not migrated into the platform wheel. The command prints what to
install instead of failing obscurely, which is the useful behaviour and the reason `studio`
keeps its group.
