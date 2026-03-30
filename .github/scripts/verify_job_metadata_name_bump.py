#!/usr/bin/env python3
"""
Fail if a batch/v1 Job's spec changed without a metadata.name change.
Job spec.template (and most of spec) is immutable in Kubernetes; Flux applies
then break when the name is reused.
"""
from __future__ import annotations

import os
import subprocess
import sys
from copy import deepcopy

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


def check_pair(path: str, old_job: dict, new_job: dict) -> list[str]:
    errors: list[str] = []
    old_name = (old_job.get("metadata") or {}).get("name")
    new_name = (new_job.get("metadata") or {}).get("name")
    old_spec = deepcopy(old_job.get("spec") or {})
    new_spec = deepcopy(new_job.get("spec") or {})
    if old_spec != new_spec and old_name == new_name:
        errors.append(
            f"{path}: Job `spec` changed but `metadata.name` is still {old_name!r}. "
            "Bump the name so Kubernetes accepts a new Job (spec is immutable)."
        )
    return errors


def resolve_base_ref() -> str:
    base = os.environ.get("BASE", "").strip()
    if not base or set(base) == {"0"}:
        try:
            return git_output(["git", "rev-parse", "HEAD~1"])
        except subprocess.CalledProcessError:
            print(
                "No BASE ref and could not resolve HEAD~1; skipping verification.",
                file=sys.stderr,
            )
            sys.exit(0)
    return base


def main() -> int:
    head = os.environ.get("HEAD", "").strip() or git_output(["git", "rev-parse", "HEAD"])
    base = resolve_base_ref()

    if base == head:
        return 0

    files = changed_job_yaml_files(base, head)
    if not files:
        return 0

    all_errors: list[str] = []
    for path in files:
        old_raw = file_at(base, path)
        new_raw = file_at(head, path)
        if new_raw is None:
            continue
        if old_raw is None:
            continue

        old_jobs = jobs_from(old_raw)
        new_jobs = jobs_from(new_raw)
        if not old_jobs and not new_jobs:
            continue
        if len(old_jobs) != len(new_jobs):
            all_errors.append(
                f"{path}: Job count changed ({len(old_jobs)} -> {len(new_jobs)}); "
                "review manually and ensure metadata.name bumps where needed."
            )
            continue
        for old_j, new_j in zip(old_jobs, new_jobs, strict=True):
            all_errors.extend(check_pair(path, old_j, new_j))

    if all_errors:
        print("Job metadata.name bump check failed:\n", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
