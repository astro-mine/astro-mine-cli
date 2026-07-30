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
  seal      sign, verify and describe artifacts
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

Fourteen names are components. Three are not, because they answer a question no single
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

## Signing something you were handed

`astro-mine seal` is the loose-file half of the supply chain: no registry, no account, no
network. `astro-mine hub` is the other half, for anything addressed by a registry reference.

```console
$ astro-mine hub keygen --out .                    # the one way to mint a keypair
$ astro-mine seal sign ice-map.tif --key cosign.key --out ice-map.sig
$ astro-mine seal verify ice-map.tif --signature ice-map.sig --key cosign.pub
ok sha256:aa6a76d39dc9565c5774eed435c5983773e4849c3a7c5f3288d9d425748f2502
```

Change one byte and it fails closed, with a message rather than a traceback:

```console
$ astro-mine seal verify ice-map.tif --signature ice-map.sig --key cosign.pub
astro-mine seal verify: verification failed: signature payload does not match the artifact digest
$ echo $?
1
```

`seal provenance` and `seal sbom` emit the other two documents `hub publish` attaches, and
`seal inspect` reads any of the three back. `--key` is **required** on `verify`: a signature
carries its own signer's public key, so checking against that alone proves nothing about who
made it.

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
