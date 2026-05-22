#!/usr/bin/env python3
"""Smoke test：编译检查每个 .py 文件，确认无语法错误。

用法：
    python3 scripts/smoke_test.py
"""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache", ".ruff_cache"}

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

passes = 0
failures = 0


def check_file(path: Path) -> None:
    global passes, failures
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"  {GREEN}PASS{RESET} {path.relative_to(ROOT)}")
        passes += 1
    except py_compile.PyCompileError as exc:
        print(f"  {RED}FAIL{RESET} {path.relative_to(ROOT)} — {exc}")
        failures += 1


def main() -> None:
    print("Real-Time Commander Demo — 语法自检\n")

    py_files = sorted(
        p for p in ROOT.rglob("*.py")
        if not any(part in SKIP_DIRS for part in p.parts)
    )

    if not py_files:
        print("未找到 .py 文件")
        sys.exit(1)

    for path in py_files:
        check_file(path)

    print()
    print(f"{GREEN}{passes} PASS{RESET} / {RED}{failures} FAIL{RESET}  ({len(py_files)} files)")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
