#!/usr/bin/env python3
"""Validate and atomically promote DMS Matugen's semantic color overlay."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts/build-theme.py"
SPEC = importlib.util.spec_from_file_location("build_theme", BUILDER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load theme validator at {BUILDER_PATH}")
BUILD_THEME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_THEME)


def read_candidate(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read Matugen candidate: {exc}") from exc
    errors = BUILD_THEME.validate_dynamic_theme(value)
    if errors:
        raise ValueError("candidate failed semantic validation:\n- " + "\n- ".join(errors))
    return value


def promote(candidate: Path, output: Path) -> None:
    if candidate.resolve() == output.resolve():
        raise ValueError("candidate and output must be different files")
    value = read_candidate(candidate)
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(value, temporary, indent=2, ensure_ascii=False)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())

        os.replace(temporary_path, output)
        temporary_path = None
        directory_fd = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    candidate.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        promote(args.candidate, args.output)
    except (OSError, ValueError) as exc:
        print(f"dynamic theme was not promoted: {exc}", file=sys.stderr)
        return 1

    print(f"promoted validated dynamic theme to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
