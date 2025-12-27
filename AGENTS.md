# Repository Guidelines

## Project Structure & Modules
- Source in `src/tclint/` with CLI entry points under `src/tclint/cli/` and command definitions in `src/tclint/commands/`.
- Tests live in `tests/`, with CLI suites in `tests/cli/` and command checks in `tests/commands/`.
- Docs and examples reside in `docs/` and `tests/data/`; utility scripts in `util/`.

## Build, Test, and Development
- Create venv and install dev deps: `python -m venv .venv && source .venv/bin/activate && pip install -e . --group dev`.
- Run full test suite: `python -m pytest`. Use `-k <pattern>` to scope, `-q` for quiet output.
- Format code: `black .`; lint: `flake8`, `mypy`, and `isort` (see `util/pre-commit`).
- CLI smoke tests: `tclint <file>` or `tclfmt <file>` from repo root; pass `-c` to point at a specific config.

## Coding Style & Naming
- Python 3.10+; follow Black style and isort ordering for Python sources; keep files ASCII unless needed.
- Use descriptive function and variable names; command specs and schema entries mirror Tcl semantics.
- Tcl output rules (indent, spaces-in-braces, etc.) live in `format.py`/`config.py`; follow those patterns when adjusting formatter or config behavior. Indentation defaults to 4 spaces unless tests/config specify otherwise.
- Add type hints when adding functions or updating function signatures. Use generics for collections (e.g. prefer `list[int]` to `typing.List[int]`), and use `typing.Optional[type]` rather than `type | None` for indicating optional types.

## Problem Solving Approach
- Make the minimum changes required to fulfill the request. Prefer incremental changes to large-scale ones.

## Testing Guidelines
- Pytest is the framework; tests mirror features (parser, CLI, commands). Add fixtures under `tests/data/` when possible.
- Name tests after behavior (e.g., `test_foreach_arg_expansion_only`). Keep assertions precise and avoid broad regex unless necessary.
- Run targeted tests before pushing; ensure new violations/config behaviors include end-to-end coverage in `tests/test_tclint.py` or CLI suites.

## Commit & Pull Request Practices
- Follow existing concise, imperative commit style (e.g., "add foreach arg spec", "fix config validation").
- PRs should describe intent, list key changes, note test coverage (`pytest` results), and mention config or CLI flags that change behavior.
- Include screenshots or snippets only when touching user-facing CLI output formatting.

## Configuration & Security Notes
- Config files resolve relative paths; dynamic plugins via config are blocked—use `--commands` CLI flag instead.
- Avoid writing to directories beyond the repo; respect default exclude/ignore patterns in `tests/data/tclint.toml` when adding fixtures.
