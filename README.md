# Astro-Mine-CLI

The command line for the [Astro-Mine](https://github.com/astro-mine) platform. One executable,
one grammar:

```
astro-mine <component> <verb> [options]
```

`astro-mine` is the **only** binary the platform installs. Everything the platform can do is
reachable by naming the component that owns it and then the verb.

```console
$ astro-mine
Components — `astro-mine <component> <verb>`:
  core      validate Core-authored formats; list them
  fleet     author, package and publish SADF assets
  worlds    author and publish world bundles
  prospect  publish resource priors
  link      publish contact plans
  sim       run and record simulated episodes
  bench     fetch, score and submit benchmark runs
  learn     train a policy and export it
  mind      validate and compose autonomy stacks
  guard     author, compile and falsify SafetySpecs
  hub       publish, discover and verify artifacts
  cloud     compile and submit cluster jobs
  studio    the design studio

Routers — these pick the owning component for you:
  validate  validate an authored document (routed to the format's owner)
  new       scaffold an authored document (routed to the format's owner)
  plugin    scaffold a plugin package (`plugin new <kind>`)

`astro-mine <component> --help` lists that component's verbs.
```

## Install

```console
$ pip install astro-mine-cli      # brings astro-mine-platform with it
$ astro-mine --version
```

The CLI depends on `astro-mine-platform`, the single distribution that ships every
`astro_mine.<component>` package. Installing the CLI installs the platform; there is nothing
else to add.

## The three routers

Thirteen names are components. Three are not, because they answer a question no single
component can: *who owns this?*

| | |
|---|---|
| `astro-mine validate <file>` | routes a document to the component that owns its schema `$id` |
| `astro-mine new <kind> <out>` | scaffolds an authored document — `asset`, `world`, `stack`, `safety` |
| `astro-mine plugin new <kind> <out>` | scaffolds a plugin package — 8 kinds, one per extension group |

`new` and `validate` are two ends of the same contract: what `new` writes, `validate` accepts.
The template belongs to the format's owner, so the two cannot drift.

```console
$ astro-mine new asset rover.yaml
$ astro-mine validate rover.yaml
OK rover.yaml (sadf)
```

## A worked path

```console
$ astro-mine bench fetch lunar-polar-ice-prospecting-v1   # pull the pinned content
$ astro-mine bench score lunar-polar-ice-prospecting-v1   # run and score a baseline
$ astro-mine sim run  lunar-polar-ice-prospecting-v1      # one episode, no Bench ceremony
$ astro-mine hub publish ./artifact --registry ./reg --key cosign.key
```

## Extending it

A package outside the platform gains a verb by registering into the `astro_mine.cli`
entry-point group — no PR here, no change to this package:

```toml
[project.entry-points."astro_mine.cli"]
myverb = "my_package.cli:command"
```

The target needs four members — `name`, `help`, `add_arguments(parser)`, `run(args) -> int`.
`astro-mine plugin new cli` writes a working one. The same contract backs three more groups:
`astro_mine.cli.validators`, `astro_mine.cli.scaffolds` and `astro_mine.cli.plugin_scaffolds`.

A third party may not take a name the platform owns. A collision is a hard error naming both
claimants, never a silent winner — which package handled your command is provenance.

## What lives here, and what does not

This package is a **thin wrapper**. A module under `astro_mine.cli` may declare arguments, read
a `Namespace`, call a platform function, format output, and map a result to an exit status. It
may not implement domain logic, define a schema, hold state between invocations, or reach into
a platform private name.

Anything a command needs that the platform does not export is a **platform** change, not a
helper smuggled in here. That rule is what keeps `astro-mine fleet package` and Fleet's own
packaging path producing byte-identical output.

See [ARCHITECTURE.md](ARCHITECTURE.md) for why the CLI is a separate distribution from the
platform it drives, and [CONTRIBUTING.md](CONTRIBUTING.md) for the rules a change here must hold.

## Licence

Apache-2.0. Copyright Astro-Mine project contributors.
