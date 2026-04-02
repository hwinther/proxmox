#!/usr/bin/env python3
"""Ensure every clusters/ subfolder that directly contains YAML is listed in Dependabot."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CLUSTERS = REPO_ROOT / "clusters"
DEPENDABOT = REPO_ROOT / ".github" / "dependabot.yml"
DEPENDABOT_REL = ".github/dependabot.yml"
YAML_SUFFIXES = (".yaml", ".yml")
MISSING_LIST_FILE = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "dependabot-cluster-missing.txt"


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


def _github_error_message(text: str) -> str:
    """Escape for ::error command body (see GitHub workflow commands docs)."""
    return (
        text.replace("%", "%25")
        .replace("\r\n", "%0D%0A")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def main() -> int:
    required = clusters_dirs_with_yaml()
    configured = dependabot_directories()
    missing = sorted(required - configured)
    if missing:
        MISSING_LIST_FILE.write_text("\n".join(missing) + "\n", encoding="utf-8")
        hint = (
            "Add under the appropriate package-ecosystem "
            '(e.g. docker "directories" list).'
        )
        for m in missing:
            msg = _github_error_message(f"Cluster directory {m} is not listed in Dependabot. {hint}")
            print(f"::error file={DEPENDABOT_REL},title=Dependabot::{msg}")
        print(
            "These cluster directories contain YAML but are not listed "
            "in .github/dependabot.yml (directory or directories):",
            file=sys.stderr,
        )
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        print(f"\n{hint}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
