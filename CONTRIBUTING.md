# Contributing to astro-mine-cli

Thanks for helping build the Astro-Mine commons. This repo follows the org-wide
governance and community-health defaults in
[`astro-mine/.github`](https://github.com/astro-mine/.github) (`GOVERNANCE.md`,
`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`).

## Development environment

**Python 3.12**, one **conda** env per repo, **uv** for dependencies.

```bash
conda create -n astro-mine-cli python=3.12
conda activate astro-mine-cli
uv sync                     # dev deps from uv.lock -- there are no runtime deps
uv run pre-commit install   # enable git hooks (once)
```

## Checks (must pass before a PR)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

CI runs the same four checks on every push and pull request, plus one more: it builds the wheel,
installs it into an **empty** virtualenv, and runs `astro-mine` there. That step is the
zero-dependency rule, checked the way a user would experience it.

## The rule that is not negotiable

**This package declares no runtime dependencies — not even `astro-mine-core`.**

It is the reason the umbrella exists as its own package instead of living inside a component
(RFC-0011 §"Alternatives considered"): an umbrella that depends on every component would drag the
whole platform into every install and break the local tier that must always work
(`conventions.md §7`). Discovery keys on the entry-point **group name**, `astro_mine.cli`, and a
provider is imported only when its verb runs.

Two consequences for a contributor:

- **Do not add a dependency to `pyproject.toml`.** `tests/test_packaging.py` will fail, and that
  test is doing its job. If a dependency genuinely becomes necessary, that is a design change and
  goes through the RFC process — not a PR.
- **Do not copy CI steps from a sibling repo wholesale.** Every other component's CI has an
  "Authenticate to private dependencies" step for the private `astro-mine-core` git source. This
  repo deliberately has none. The workflow comments say so at the exact line where a copy-paste
  would land.

## Adding a verb — you probably do not want this repo

A component contributes a subcommand from **its own** repo by declaring an entry point:

```toml
[project.entry-points."astro_mine.cli"]
train = "astro_mine.learn.cli:umbrella"
```

That is the whole contract. No component imports the umbrella, and the umbrella imports no
component to list it. If you find yourself editing this package to add a verb, the extension point
is not being used as designed — say so in an issue rather than working around it.

## Workflow

- Branch from `main`; PRs are **squash-merged** and the branch auto-deleted.
- Reference the issue in the PR, and the RFC section a change implements
  ([RFC-0011](https://github.com/astro-mine/docs/blob/main/rfc/0011-umbrella-cli.md) §1–§7).
- Command naming is normative in
  [`conventions.md §13`](https://github.com/astro-mine/docs/blob/main/architecture/conventions.md) —
  direct binaries `astro-mine-<package>`, umbrella `astro-mine <verb>`. New CLIs are born prefixed.

## Conventions

Plugins-over-patches, library-before-service, and the narrow-waist discipline. See
[`docs/architecture/conventions.md`](https://github.com/astro-mine/docs/blob/main/architecture/conventions.md)
and [ARCHITECTURE.md](ARCHITECTURE.md) for this package's own decisions.
