#!/usr/bin/env python3
"""
Bump batch/v1 Job metadata.name when spec changed vs base but name was not bumped.
Used after a maintainer adds the configured label on a PR. Logic matches
verify_job_metadata_name_bump.py.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import yaml


def git_output(args: list[str]) -> str:
    return subprocess.check_output(args, text=True).strip()


def changed_job_yaml_files(base: str, head: str) -> list[str]:
    out = git_output(["git", "diff", "--name-only", base, head])
    paths: list[str] = []
    for line in out.splitlines():
        p = line.strip()
        if not p:
            continue
        if p.endswith("/job.yaml") or p == "job.yaml":
            paths.append(p)
    return paths


def file_at(ref: str, path: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{path}"], text=True
        )
    except subprocess.CalledProcessError:
        return None


def jobs_from(content: str) -> list[dict]:
    return [
        doc
        for doc in yaml.safe_load_all(content)
        if isinstance(doc, dict) and doc.get("kind") == "Job"
    ]


def bump_name(name: str) -> str:
    """Increment trailing -vNNN (preserve width); else trailing -bN; else append -b1."""
    m = re.match(r"^(.*-v)(\d+)$", name)
    if m:
        prefix, digits = m.group(1), m.group(2)
        n = int(digits) + 1
        width = len(digits)
        return f"{prefix}{n:0{width}d}"
    m = re.match(r"^(.*-b)(\d+)$", name)
    if m:
        prefix, digits = m.group(1), m.group(2)
        return f"{prefix}{int(digits) + 1}"
    return f"{name}-b1"


def needs_bump(old_job: dict, new_job: dict) -> bool:
    old_name = (old_job.get("metadata") or {}).get("name")
    new_name = (new_job.get("metadata") or {}).get("name")
    old_spec = deepcopy(old_job.get("spec") or {})
    new_spec = deepcopy(new_job.get("spec") or {})
    return old_spec != new_spec and old_name == new_name


def job_indices_in_docs(docs: list) -> list[int]:
    return [
        i
        for i, d in enumerate(docs)
        if isinstance(d, dict) and d.get("kind") == "Job"
    ]


def process_file(path: str, base: str, head: str) -> bool:
    old_raw = file_at(base, path)
    new_raw = file_at(head, path)
    if old_raw is None or new_raw is None:
        return False

    old_jobs = jobs_from(old_raw)
    new_jobs = jobs_from(new_raw)
    if not old_jobs and not new_jobs:
        return False
    if len(old_jobs) != len(new_jobs):
        print(
            f"{path}: Job count changed ({len(old_jobs)} -> {len(new_jobs)}); "
            "cannot auto-bump.",
            file=sys.stderr,
        )
        sys.exit(1)

    bump_zip_indices = [
        i
        for i, (oj, nj) in enumerate(zip(old_jobs, new_jobs, strict=True))
        if needs_bump(oj, nj)
    ]
    if not bump_zip_indices:
        return False

    p = Path(path)
    text = p.read_text(encoding="utf-8")
    docs = list(yaml.safe_load_all(text))
    indices = job_indices_in_docs(docs)
    if len(indices) != len(new_jobs):
        print(
            f"{path}: Document Job count does not match git diff; cannot auto-bump.",
            file=sys.stderr,
        )
        sys.exit(1)

    replacements: list[tuple[str, str]] = []
    for z in bump_zip_indices:
        doc_i = indices[z]
        doc = docs[doc_i]
        meta = doc.get("metadata") or {}
        cur = meta.get("name")
        if not isinstance(cur, str):
            print(f"{path}: Job at index {z} has no string metadata.name.", file=sys.stderr)
            sys.exit(1)
        replacements.append((cur, bump_name(cur)))

    out = text
    for old, new in replacements:
        pat = re.compile(
            rf"^([ \t]*name:\s+){re.escape(old)}\s*$",
            re.MULTILINE,
        )
        found = list(pat.finditer(out))
        if len(found) != 1:
            print(
                f"{path}: expected exactly one line `name: {old!r}`; "
                f"found {len(found)}. Edit manually or adjust job.yaml layout.",
                file=sys.stderr,
            )
            sys.exit(1)
        out = pat.sub(rf"\g<1>{new}", out, count=1)

    p.write_text(out, encoding="utf-8", newline="\n")
    print(f"Bumped metadata.name in {path}", file=sys.stderr)
    return True


def main() -> int:
    base = os.environ.get("BASE", "").strip()
    head = os.environ.get("HEAD", "").strip()
    if not base or not head:
        print("BASE and HEAD must be set.", file=sys.stderr)
        return 1

    if base == head:
        return 0

    any_bumped = False
    for path in changed_job_yaml_files(base, head):
        if process_file(path, base, head):
            any_bumped = True

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"bumped={'true' if any_bumped else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
