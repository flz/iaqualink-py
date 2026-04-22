from __future__ import annotations

import importlib
import sys
from typing import Any

_MISSING_CLI_DEPS_MESSAGE = (
    "The iaqualink CLI requires optional dependencies. "
    "Install with 'pip install \"iaqualink[cli]\"' or "
    "'uv add \"iaqualink[cli]\"'."
)


def _load_cli_module() -> Any:
    try:
        return importlib.import_module("iaqualink.cli.app")
    except ModuleNotFoundError as exc:
        if exc.name in {"typer", "yaml"}:
            print(_MISSING_CLI_DEPS_MESSAGE, file=sys.stderr)
            raise SystemExit(1) from exc
        raise


def main() -> None:
    _load_cli_module().main()


def __getattr__(name: str) -> Any:
    if name == "main":
        return main
    if name == "app":
        return _load_cli_module().app
    raise AttributeError(name)


__all__ = ["app", "main"]
