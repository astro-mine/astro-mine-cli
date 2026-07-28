# Contributing to astro-mine-cli

## The one rule

This package is a **thin wrapper** over `astro-mine-platform`. A module under `astro_mine.cli`
may:

- declare argparse arguments
- read a parsed `Namespace`
- call a platform function
- format output for a human or for `--json`
- map a result to an exit status

It may **not**:

- implement domain logic
- define a schema or data model
- hold state between invocations
- import a platform private (`_`-prefixed) name

If a command needs something the platform does not export, that is a **platform** change — open
an issue on `astro-mine-platform` to promote the function. Do not add a helper here.

This is not stylistic. `astro-mine fleet package` and Fleet's own packaging manifest must
produce byte-identical canonical JSON; they do so only because both call the same exported
function. A local reimplementation would diverge silently and the divergence would be baked
into every artifact published afterwards.

## Adding a verb to an existing component

Add it to that component's parser in `src/astro_mine/cli/<component>/__init__.py`, and add the
handler beside it. Then update the parity fixture **in the same commit** — see below.

## Adding a component

1. Add a row to `COMPONENTS` in `src/astro_mine/cli/_registry.py`. It is plain strings on
   purpose: `astro-mine --help` must render without importing anything.
2. Create `src/astro_mine/cli/<component>/__init__.py` exposing a module-level `command` object
   with `name`, `help`, `add_arguments(parser)` and `run(args) -> int`.
3. Import platform symbols **inside** your handlers, not at module scope, so
   `astro-mine <component> --help` stays cheap.

## The parity fixture

`tests/fixtures/parser-snapshot.json` is the contract: every verb's arguments as the platform's
own binaries declared them. `tests/test_parser_parity.py` compares the live parsers against it.

**Regenerating the fixture to make a failing test pass is not a fix.** A failure means a flag,
default or help string changed. If that change is intended, say so in the commit message and
move the fixture in that same commit, so the diff shows what a user's command line now does
differently. If it is not intended, you have just been told about a bug.

## Running the tests

```console
$ uv sync
$ uv run pytest                      # unit + parity + dispatch
$ uv run pytest -m integration       # builds a wheel, installs into a throwaway venv
$ uv run ruff check . && uv run mypy src
```

The integration lane is the only place the packaging metadata — the console script, and
entry-point discovery *across* distributions — is exercised for real. Do not weaken it to make
it pass; if it cannot run in your environment, say so rather than adding `--no-deps`.

## Commit and PR conventions

Follow the existing `git log`: a declarative subject under ~72 characters, and a body that
explains *why*, not what the diff already shows. Reference the issue in the body.
