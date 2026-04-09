#!/usr/bin/env python3
"""
Scan Git-tracked YAML under clusters/ for ghcr.io/hwinther/* container images and run
cosign verify-attestation the same way Kyverno supply-chain policies expect:

  - Issuer: https://token.actions.githubusercontent.com
  - Identity (default ghcr.io/hwinther/* except SDR): reusable-workflows
    …/(docker|dotnet)-container.yml@refs/tags/v1
  - Identity (ghcr.io/hwinther/proxmox/sdr/*): hwinther/proxmox build-*.yaml @ refs/heads/main or refs/tags/*

Why images like clutterstock/migrator often fail Kyverno:
  Attestations may be missing entirely, or cosign signed them with a *different* workflow
  identity (e.g. hwinther/clutterstock/.github/workflows/... @ refs/heads/main) because
  the build used a repo-local composite action instead of workflow_call to reusable-workflows@v1.

Requires: cosign on PATH, network to ghcr.io + Rekor. For private GHCR packages:
  echo $GITHUB_TOKEN | cosign login ghcr.io -u USER --password-stdin

For private GHCR packages, login first:
$env:GITHUB_TOKEN = gh auth token
echo $env:GITHUB_TOKEN | cosign login ghcr.io -u hwinther --password-stdin

Usage:
  python scripts/verify_ghcr_hwinther_attestations.py
  python scripts/verify_ghcr_hwinther_attestations.py --roots clusters/production
  python scripts/verify_ghcr_hwinther_attestations.py --loose-identity
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

IMAGE_RE = re.compile(
    r"^\s*image:\s*(ghcr\.io/hwinther/[^\s#'\"]+)\s*(?:#.*)?$",
    re.MULTILINE,
)

KYVERNO_ISSUER = r"^https://token\.actions\.githubusercontent\.com$"
KYVERNO_IDENTITY = (
    r"^https://github.com/hwinther/reusable-workflows/\.github/workflows/"
    r"(docker|dotnet)-container\.yml@refs/tags/v1$"
)
# Must stay in sync with bases/kyverno-supply-chain clusterpolicy-* SDR verifyImages entry.
PROXMOX_SDR_IDENTITY = (
    r"^https://github.com/hwinther/proxmox/\.github/workflows/" r"build-[a-z0-9-]+\.ya?ml@refs/(heads/main|tags/.+)$"
)


def kyverno_identity_for_image(image: str, loose: bool) -> str:
    if loose:
        return ".*"
    if image.startswith("ghcr.io/hwinther/proxmox/sdr/"):
        return PROXMOX_SDR_IDENTITY
    return KYVERNO_IDENTITY


def verify_image_attestations(img: str, loose: bool) -> int:
    """Run cyclonedx + vuln cosign checks; print lines; return failure count."""
    ident = kyverno_identity_for_image(img, loose)
    fails = 0
    for ptype, label in (
        ("cyclonedx", "CycloneDX (wsh-require-cyclonedx-sbom)"),
        ("vuln", "vuln (wsh-require-cosign-vuln-attestation)"),
    ):
        code, blob = run_cosign_verify_attestation(img, ptype, ident)
        status = "OK" if code == 0 else "FAIL"
        if code != 0:
            fails += 1
        print(f"    [{label}] {status}")
        if code != 0 and blob:
            first = blob.splitlines()[0] if blob else ""
            if len(first) > 200:
                first = first[:200] + "…"
            print(f"        {first}")
    return fails


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def collect_images(roots: list[Path]) -> dict[str, list[str]]:
    """image ref -> list of relative file paths (dedup refs, keep first-seen paths)."""
    found: dict[str, set[str]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.yaml")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as e:
                print(f"skip read {path}: {e}", file=sys.stderr)
                continue
            for m in IMAGE_RE.finditer(text):
                img = m.group(1).strip()
                if not img:
                    continue
                found.setdefault(img, set()).add(str(path.relative_to(repo_root())))
    return {k: sorted(v) for k, v in sorted(found.items())}


def run_cosign_verify_attestation(
    image: str,
    predicate_type: str,
    identity_regexp: str,
) -> tuple[int, str]:
    cmd = [
        "cosign",
        "verify-attestation",
        image,
        "--type",
        predicate_type,
        "--certificate-oidc-issuer-regexp",
        KYVERNO_ISSUER,
        "--certificate-identity-regexp",
        identity_regexp,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--roots",
        nargs="*",
        default=["clusters"],
        help="Directories to scan (default: clusters)",
    )
    ap.add_argument(
        "--loose-identity",
        action="store_true",
        help="Use .* for certificate identity (any GitHub Actions signer); "
        "useful to see if *some* attestation exists vs Kyverno-strict signer.",
    )
    args = ap.parse_args()

    root = repo_root()
    scan_roots = [(root / r).resolve() for r in args.roots]
    images = collect_images(scan_roots)
    if not images:
        print("No ghcr.io/hwinther/* images found.", file=sys.stderr)
        return 1

    mode = (
        "loose identity (any GH Actions signer)"
        if args.loose_identity
        else "Kyverno-strict (reusable-workflows@v1 or proxmox/sdr build-*.yaml)"
    )

    print(f"Found {len(images)} unique image reference(s); cosign mode: {mode}\n")

    fails = 0
    for img, paths in images.items():
        print(f"=== {img}")
        for p in paths[:5]:
            print(f"    {p}")
        if len(paths) > 5:
            print(f"    ... +{len(paths) - 5} more")

        ident = kyverno_identity_for_image(img, args.loose_identity)
        if not args.loose_identity:
            bucket = "proxmox/sdr" if ident == PROXMOX_SDR_IDENTITY else "reusable-workflows@v1"
            print(f"    (Kyverno identity bucket: {bucket})")

        fails += verify_image_attestations(img, args.loose_identity)
        print()

    print(f"Summary: {fails} failing check(s) across {len(images)} image(s).")
    return 0 if fails == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
