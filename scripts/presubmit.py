#!/usr/bin/env python3
"""Presubmit checks. Run locally by the pre-push hook and in CI on every PR.

Deliberately dependency-free so it runs anywhere without a setup step.

Checks grow with the repo: documentation checks apply from day one, code checks
switch themselves on once `host/` exists.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parent.parent

# [text](target) — captures the target, ignoring images and anchors handled below
MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")

SKIP_DIRS: frozenset[str] = frozenset({".git", "__pycache__", ".venv", "node_modules"})


class Failure(Exception):
    """A check failed. Message is shown to the user verbatim."""


def markdown_files() -> list[Path]:
    return sorted(
        p
        for p in REPO_ROOT.rglob("*.md")
        if not SKIP_DIRS.intersection(p.relative_to(REPO_ROOT).parts)
    )


def check_internal_links() -> list[str]:
    """Every relative markdown link must resolve to a file that exists.

    Broken links in a docs-only repo are the entire failure surface, so this is
    the check that actually earns its place today.
    """
    problems: list[str] = []
    for md in markdown_files():
        text: str = md.read_text(encoding="utf-8")
        for target in MD_LINK.findall(text):
            target = target.strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_part: str = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved: Path = (md.parent / path_part).resolve()
            if not resolved.exists():
                rel: Path = md.relative_to(REPO_ROOT)
                problems.append(f"{rel}: broken link -> {target}")
    return problems


def check_no_trailing_whitespace() -> list[str]:
    problems: list[str] = []
    for md in markdown_files():
        for lineno, line in enumerate(
            md.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line != line.rstrip():
                rel = md.relative_to(REPO_ROOT)
                problems.append(f"{rel}:{lineno}: trailing whitespace")
    return problems


def check_safety_doc_present() -> list[str]:
    """SAFETY.md must exist and must state the fail-closed rule.

    This project aims water at animals unattended. If the safety document ever
    quietly loses its central rule, that is exactly the regression worth failing
    a build over.
    """
    safety: Path = REPO_ROOT / "SAFETY.md"
    if not safety.exists():
        return ["SAFETY.md is missing"]
    text: str = safety.read_text(encoding="utf-8").lower()
    if "normally-closed" not in text and "normally closed" not in text:
        return ["SAFETY.md no longer states the normally-closed valve rule"]
    return []


def check_python() -> list[str]:
    """Code checks, active only once there is code."""
    host: Path = REPO_ROOT / "host"
    if not host.exists():
        return []
    problems: list[str] = []
    tests: Path = host / "tests"
    if tests.exists():
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
            cwd=host,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            problems.append("unit tests failed:\n" + result.stdout + result.stderr)
    return problems


CHECKS: list[tuple[str, object]] = [
    ("internal markdown links", check_internal_links),
    ("trailing whitespace", check_no_trailing_whitespace),
    ("safety doc invariants", check_safety_doc_present),
    ("python", check_python),
]


def main() -> int:
    failed: bool = False
    for name, fn in CHECKS:
        problems: list[str] = fn()  # type: ignore[operator]
        if problems:
            failed = True
            print(f"  x {name}")
            for problem in problems:
                print(f"      {problem}")
        else:
            print(f"  . {name}")
    if failed:
        print("\npresubmit failed")
        return 1
    print("\npresubmit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
