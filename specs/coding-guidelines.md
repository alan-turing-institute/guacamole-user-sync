# Coding Guidelines

Conventions for working in this codebase, beyond what `ruff`/`black`/`mypy`
already enforce.

## Tooling

- Run tests and code quality tools through **Hatch**, matching the CI/CD
  pipeline (`.github/workflows/test_code.yaml`, `lint_code.yaml`):
  - `hatch run test:all` — runs the test suite and reports coverage.
  - `hatch run lint:all` — runs formatting, style, and type checks.
  - Prefer these over invoking `pytest`/`ruff`/`black`/`mypy` directly, so
    local runs match what CI actually checks.

## Type annotations

- Use precise type annotations wherever possible — prefer the specific type
  (e.g. `list[GuacamoleEntity]`, `Generator[PostgreSQLBackend, None, None]`)
  over broad ones (`Any`, `object`) unless no more specific type is
  available (e.g. third-party callback signatures typed `Any` upstream).

## Method/function length

- Prefer brief, focused methods/functions over long ones — this keeps code
  readable and each piece easy to reason about in isolation.
- If a method/function grows too long or starts doing several distinct
  things, split it into smaller, well-named helpers rather than letting it
  keep growing.

## Docstrings

- Keep docstrings brief: at most two sentences stating the purpose of the
  method/class/type. Skip parameter/return sections and usage examples.

## Comments

- Keep in-line comments brief. If a comment needs more than a sentence or two
  to explain *why*, link out to an external source (e.g. documentation,
  issue, upstream reference) instead of writing the explanation inline.

## Testing

- Aim to cover the maximum number of code paths with the minimum number of
  tests. Before adding a new test, check whether an existing test (or one
  planned alongside it) already exercises the same path as a side effect —
  if so, don't add a separate, narrower test just to re-assert it in
  isolation.
- Avoid overlapping tests: two tests that fail for the same underlying
  reason are redundant, not extra safety. Prefer extending an existing
  test's assertions (when it already puts the system in the right state) over
  writing a new test that re-creates similar state to check something
  adjacent.
