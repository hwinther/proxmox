#!/usr/bin/env python3
"""Ensure every clusters/ subfolder that directly contains YAML is listed in Dependabot."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CLUSTERS = REPO_ROOT / "clusters"
DEPENDABOT = REPO_ROOT / ".github" / "dependabot.yml"
YAML_SUFFIXES = (".yaml", ".yml")


def clusters_dirs_with_yaml() -> set[str]:
    """Paths like /clusters/foo/bar for dirs that have at least one *.yaml/*.yml child."""
    found: set[str] = set()
    if not CLUSTERS.is_dir():
        return found
    for path in CLUSTERS.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in YAML_SUFFIXES:
            continue
        rel = path.parent.relative_to(REPO_ROOT).as_posix()
        found.add(f"/{rel}")
    return found


def dependabot_directories() -> set[str]:
    with DEPENDABOT.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    dirs: set[str] = set()
    for entry in data.get("updates") or []:
        d = entry.get("directory")
        if isinstance(d, str):
            dirs.add(d)
        for item in entry.get("directories") or []:
            if isinstance(item, str):
                dirs.add(item)
    return dirs


def main() -> int:
    required = clusters_dirs_with_yaml()
    configured = dependabot_directories()
    missing = sorted(required - configured)
    if missing:
        print(
            "These cluster directories contain YAML but are not listed "
            "in .github/dependabot.yml (directory or directories):",
            file=sys.stderr,
        )
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        print(
            "\nAdd each path under the appropriate package-ecosystem "
            '(e.g. docker "directories" list).',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
