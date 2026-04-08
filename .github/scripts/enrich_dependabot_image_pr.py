#!/usr/bin/env python3
"""
For Dependabot PRs that bump digest-pinned container images:
  - Resolve semver / version labels from the OCI config for the new digest.
  - Rewrite trailing YAML comments on image: lines when the digest changed.
  - Append or refresh a PR body section with GitHub Release notes when available.

Stdlib only. Intended to run in GitHub Actions on ubuntu-latest.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

IMAGE_LINE_RE = re.compile(
    r"^([ \t]*image:\s+)([^#\n]+?)(\s*(?:#\s*(.*))?)\s*$",
    re.IGNORECASE,
)
BODY_START = "<!-- image-digest-release-notes:auto -->"
BODY_END = "<!-- /image-digest-release-notes:auto -->"

ACCEPT_MANIFEST = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)
ACCEPT_CONFIG = "application/vnd.docker.container.image.v1+json, application/vnd.oci.image.config.v1+json"


@dataclass
class ImagePin:
    indent_and_key: str  # "        image: "
    full_ref: str  # ghcr.io/foo/bar@sha256:...
    comment: str | None
    line_index: int


@dataclass
class RegistryTarget:
    registry_host: str
    repository: str  # path for /v2/{repository}/manifests/...


def _run_git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out


def _git_show(sha: str, path: str) -> str | None:
    try:
        return _run_git("show", f"{sha}:{path}")
    except subprocess.CalledProcessError:
        return None


def _changed_yaml_paths(base: str, head: str) -> list[str]:
    raw = _run_git("diff", "--name-only", f"{base}...{head}")
    paths: list[str] = []
    for line in raw.splitlines():
        p = line.strip()
        if p.endswith((".yaml", ".yml")):
            paths.append(p)
    return paths


def _parse_image_lines(content: str) -> list[ImagePin]:
    lines = content.splitlines()
    found: list[ImagePin] = []
    for i, line in enumerate(lines):
        m = IMAGE_LINE_RE.match(line)
        if not m:
            continue
        ref = m.group(2).strip()
        if "@sha256:" not in ref:
            continue
        cmt = m.group(4)
        if cmt is not None:
            cmt = cmt.strip()
        found.append(
            ImagePin(
                indent_and_key=m.group(1),
                full_ref=ref,
                comment=cmt if cmt else None,
                line_index=i,
            )
        )
    return found


def _image_base(ref: str) -> str:
    """Strip @sha256:... for stable matching across revisions."""
    if "@sha256:" in ref:
        return ref.split("@sha256:", 1)[0]
    return ref


def _digest(ref: str) -> str:
    part = ref.split("@sha256:", 1)[1]
    hexpart = part.split()[0]
    return f"sha256:{hexpart}"


def _parse_registry_repository(image_name: str) -> RegistryTarget | None:
    """
    image_name is without digest, e.g. ghcr.io/hwinther/clutterstock/api
    """
    name = image_name.strip()
    if name.startswith("ghcr.io/"):
        rest = name[len("ghcr.io/") :]
        return RegistryTarget("ghcr.io", rest)
    if name.startswith("docker.io/"):
        rest = name[len("docker.io/") :]
        return RegistryTarget("registry-1.docker.io", rest)
    if name.startswith("registry-1.docker.io/"):
        rest = name[len("registry-1.docker.io/") :]
        return RegistryTarget("registry-1.docker.io", rest)
    if name.startswith("quay.io/"):
        rest = name[len("quay.io/") :]
        return RegistryTarget("quay.io", rest)
    return None


def _docker_hub_token(repository: str) -> str:
    scope = f"repository:{repository}:pull"
    url = (
        "https://auth.docker.io/token?"
        + urllib.parse.urlencode({"service": "registry.docker.io", "scope": scope})
    )
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    token = data.get("token") or data.get("access_token")
    if not token:
        raise RuntimeError("docker hub token response missing token")
    return str(token)


def _request(
    url: str,
    headers: dict[str, str],
    method: str = "GET",
    data: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.getcode(), dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _auth_headers(target: RegistryTarget) -> dict[str, str]:
    h: dict[str, str] = {"Accept": ACCEPT_MANIFEST}
    if target.registry_host == "ghcr.io":
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            raise RuntimeError("GITHUB_TOKEN required for ghcr.io")
        h["Authorization"] = f"Bearer {token}"
        return h
    if target.registry_host == "registry-1.docker.io":
        tok = _docker_hub_token(target.repository)
        h["Authorization"] = f"Bearer {tok}"
        return h
    if target.registry_host == "quay.io":
        return h
    raise RuntimeError(f"unsupported registry {target.registry_host}")


def _is_index(media_type: str | None) -> bool:
    if not media_type:
        return False
    return "image.index" in media_type or "manifest.list" in media_type


def _pick_child_digest(manifest: dict[str, Any]) -> str | None:
    """Prefer linux/amd64 from an index/list."""
    manifests = manifest.get("manifests")
    if not isinstance(manifests, list):
        return None
    preferred: list[tuple[int, str]] = []
    for i, desc in enumerate(manifests):
        if not isinstance(desc, dict):
            continue
        d = desc.get("digest")
        if not isinstance(d, str):
            continue
        plat = desc.get("platform") or {}
        if isinstance(plat, dict) and plat.get("os") == "linux" and plat.get("architecture") == "amd64":
            preferred.append((0, d))
        else:
            preferred.append((1, d))
    preferred.sort(key=lambda x: x[0])
    return preferred[0][1] if preferred else None


def _fetch_manifest_json(
    target: RegistryTarget,
    ref: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    url = f"https://{target.registry_host}/v2/{target.repository}/manifests/{ref}"
    status, rh, body = _request(url, headers)
    if status != 200:
        raise RuntimeError(f"manifest {url} -> HTTP {status}: {body[:500]!r}")
    media_type = rh.get("Content-Type", "").split(";")[0].strip()
    doc = json.loads(body.decode())
    if _is_index(media_type) or "manifests" in doc:
        child = _pick_child_digest(doc)
        if not child:
            raise RuntimeError("could not pick child manifest from index")
        return _fetch_manifest_json(target, child, headers)
    return doc


def _fetch_config_labels(target: RegistryTarget, config_digest: str, headers: dict[str, str]) -> dict[str, str]:
    blob_headers = {
        "Authorization": headers.get("Authorization", ""),
        "Accept": ACCEPT_CONFIG,
    }
    url = f"https://{target.registry_host}/v2/{target.repository}/blobs/{config_digest}"
    status, _, body = _request(url, {k: v for k, v in blob_headers.items() if v})
    if status != 200:
        raise RuntimeError(f"config blob HTTP {status}")
    cfg = json.loads(body.decode())
    labels = cfg.get("config", {}).get("Labels")
    if isinstance(labels, dict):
        return {str(k): str(v) for k, v in labels.items() if v is not None}
    alt = cfg.get("container_config", {}).get("Labels")
    if isinstance(alt, dict):
        return {str(k): str(v) for k, v in alt.items() if v is not None}
    return {}


def oci_version_label(image_ref_with_digest: str) -> str | None:
    if "@sha256:" not in image_ref_with_digest:
        return None
    base = _image_base(image_ref_with_digest)
    target = _parse_registry_repository(base)
    if not target:
        return None
    try:
        headers = _auth_headers(target)
    except Exception:
        return None
    digest = _digest(image_ref_with_digest)
    try:
        man = _fetch_manifest_json(target, digest, headers)
    except Exception:
        return None
    cfg_desc = man.get("config")
    if not isinstance(cfg_desc, dict):
        return None
    cfg_digest = cfg_desc.get("digest")
    if not isinstance(cfg_digest, str):
        return None
    try:
        labels = _fetch_config_labels(target, cfg_digest, headers)
    except Exception:
        return None
    for key in (
        "org.opencontainers.image.version",
        "org.opencontainers.image.ref.name",
        "version",
    ):
        val = labels.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    rev = labels.get("org.opencontainers.image.revision")
    if rev and isinstance(rev, str) and rev.strip():
        if len(rev.strip()) <= 12 and all(c in "0123456789abcdef" for c in rev.strip().lower()):
            return None
        if re.match(r"^v?\d+\.\d+", rev.strip()):
            return rev.strip()
    return None


def _github_repo_hint(image_base_name: str) -> tuple[str, str] | None:
    """Map a container image name (no digest) to a likely GitHub owner/repo."""
    if image_base_name.startswith("ghcr.io/"):
        parts = image_base_name[len("ghcr.io/") :].split("/")
        if len(parts) < 2:
            return None
        return parts[0], parts[1]
    if image_base_name.startswith("docker.io/"):
        rest = image_base_name[len("docker.io/") :]
        parts = rest.split("/")
        if parts[0] == "library" and len(parts) >= 2:
            return "docker-library", parts[1]
        if len(parts) >= 2:
            return parts[0], parts[1]
    if image_base_name.startswith("quay.io/"):
        parts = image_base_name[len("quay.io/") :].split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
    return None


def _release_tag_candidates(version: str, image_base_name: str) -> list[str]:
    v = version.strip()
    seen: list[str] = []
    for cand in (v, v.lstrip("v"), f"v{v.lstrip('v')}"):
        if cand and cand not in seen:
            seen.append(cand)
    parts = image_base_name.split("/")
    component = parts[-1] if parts else ""
    bare = v.lstrip("v")
    for prefix in (component, f"{component}/v", f"{component}/"):
        if component:
            for c in (f"{prefix}{bare}", f"{prefix}{v}", f"{prefix}v{bare}"):
                if c not in seen:
                    seen.append(c)
    return seen


def _github_release_body(gh_repo: str, tag: str, token: str) -> str | None:
    url = f"https://api.github.com/repos/{gh_repo}/releases/tags/{urllib.parse.quote(tag)}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        return None
    except Exception:
        return None
    body = data.get("body")
    return body if isinstance(body, str) and body.strip() else None


def _fetch_release_notes_for_image(
    image_base_name: str, version: str, token: str
) -> tuple[str | None, str | None, str | None]:
    hint = _github_repo_hint(image_base_name)
    if not hint:
        return None, None, None
    gh_repo = f"{hint[0]}/{hint[1]}"
    for tag in _release_tag_candidates(version, image_base_name):
        body = _github_release_body(gh_repo, tag, token)
        if body:
            return gh_repo, tag, body
    return None, None, None


def _pins_by_base_sorted(content: str) -> dict[str, list[ImagePin]]:
    g: dict[str, list[ImagePin]] = defaultdict(list)
    for p in _parse_image_lines(content):
        g[_image_base(p.full_ref)].append(p)
    for pins in g.values():
        pins.sort(key=lambda x: x.line_index)
    return g


def _merge_pins(base_content: str, head_content: str) -> list[tuple[ImagePin, ImagePin]]:
    """Pair pins by image repository (ignoring digest), in source order."""
    bg = _pins_by_base_sorted(base_content)
    hg = _pins_by_base_sorted(head_content)
    pairs: list[tuple[ImagePin, ImagePin]] = []
    for key, hlist in hg.items():
        blist = bg.get(key, [])
        for bpin, hpin in zip(blist, hlist):
            if _digest(bpin.full_ref) != _digest(hpin.full_ref):
                pairs.append((bpin, hpin))
    return pairs


def _replace_pr_body_section(original: str, new_section: str) -> str:
    if BODY_START in original and BODY_END in original:
        pre, rest = original.split(BODY_START, 1)
        _, post = rest.split(BODY_END, 1)
        return f"{pre.rstrip()}\n\n{BODY_START}\n{new_section.strip()}\n{BODY_END}\n{post.lstrip()}"
    sep = "\n\n" if original.strip() else ""
    return f"{original.rstrip()}{sep}{BODY_START}\n{new_section.strip()}\n{BODY_END}\n"


@dataclass
class EnrichmentRecord:
    image_base: str
    version: str
    gh_repo: str | None = None
    gh_tag: str | None = None
    release_body: str | None = None


def main() -> int:
    base = os.environ.get("BASE_SHA", "")
    head = os.environ.get("HEAD_SHA", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    pr_number = os.environ.get("PR_NUMBER", "")

    if not base or not head or not repo or not token or not pr_number:
        print("Missing BASE_SHA, HEAD_SHA, GITHUB_REPOSITORY, GITHUB_TOKEN, or PR_NUMBER", file=sys.stderr)
        return 1

    changed = _changed_yaml_paths(base, head)
    if not changed:
        print("No changed YAML; nothing to do.")
        _write_outputs(False, False, "")
        return 0

    file_edits: dict[str, str] = {}
    oci_cache: dict[str, str | None] = {}
    release_cache: dict[tuple[str, str], tuple[str | None, str | None, str | None]] = {}

    for path in changed:
        btxt = _git_show(base, path)
        htxt = _git_show(head, path)
        if btxt is None or htxt is None:
            continue
        pairs = _merge_pins(btxt, htxt)
        if not pairs:
            continue
        lines = htxt.splitlines()
        modified = False
        for bpin, hpin in pairs:
            cache_key = hpin.full_ref
            if cache_key not in oci_cache:
                oci_cache[cache_key] = oci_version_label(hpin.full_ref)
            ver = oci_cache[cache_key]
            if not ver:
                continue

            # Align comment with OCI label when digest changed (idempotent if already correct).
            new_line = f"{hpin.indent_and_key}{hpin.full_ref} # {ver}"
            if lines[hpin.line_index] != new_line:
                lines[hpin.line_index] = new_line
                modified = True

            rk = (_image_base(hpin.full_ref), ver)
            if rk not in release_cache:
                release_cache[rk] = _fetch_release_notes_for_image(rk[0], ver, token)
        if modified:
            ends_nl = htxt.endswith("\n")
            file_edits[path] = "\n".join(lines) + ("\n" if ends_nl else "")

    pr_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    req_get = urllib.request.Request(
        pr_url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req_get, timeout=60) as resp:
        pr = json.load(resp)
    pr_body = pr.get("body") or ""

    deduped_notes: list[EnrichmentRecord] = [
        EnrichmentRecord(
            image_base=k[0],
            version=k[1],
            gh_repo=v[0],
            gh_tag=v[1],
            release_body=v[2],
        )
        for k, v in sorted(release_cache.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    ]

    section_lines: list[str] = [
        "## Image digest release notes (auto-generated)",
        "",
        "Versions below are taken from OCI image labels on the pinned digest. Release text is from the linked GitHub release when it exists.",
        "",
    ]
    for rec in deduped_notes:
        section_lines.append(f"### `{rec.image_base}` → **{rec.version}**")
        section_lines.append("")
        if rec.gh_repo and rec.gh_tag and rec.release_body:
            url = f"https://github.com/{rec.gh_repo}/releases/tag/{rec.gh_tag}"
            section_lines.append(f"*Sourced from [{rec.gh_repo} `{rec.gh_tag}`]({url}).*")
            section_lines.append("")
            section_lines.append("<details>")
            section_lines.append("<summary>Release notes</summary>")
            section_lines.append("")
            section_lines.append(rec.release_body)
            section_lines.append("")
            section_lines.append("</details>")
        else:
            section_lines.append(
                "*No matching GitHub release was found for this image (private registry, different tagging scheme, or third-party image).*"
            )
        section_lines.append("")

    new_section = "\n".join(section_lines).strip()
    new_pr_body = (
        _replace_pr_body_section(pr_body, new_section) if deduped_notes else pr_body
    )

    commit_needed = bool(file_edits)
    body_needed = bool(deduped_notes) and new_pr_body != pr_body

    if file_edits:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        for rel, new_text in file_edits.items():
            abs_path = os.path.join(root, rel)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_text)

    if body_needed:
        patch = json.dumps({"body": new_pr_body}).encode()
        req_patch = urllib.request.Request(
            pr_url,
            data=patch,
            method="PATCH",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        urllib.request.urlopen(req_patch, timeout=60)

    _write_outputs(
        commit_needed,
        body_needed,
        "\n".join(section_lines) if deduped_notes else "",
    )
    return 0


def _write_outputs(commit: bool, body_updated: bool, summary: str) -> None:
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"commit_needed={'true' if commit else 'false'}\n")
            f.write(f"pr_body_updated={'true' if body_updated else 'false'}\n")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path and summary.strip():
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n## Dependabot image enrichment\n\n")
            f.write(summary)
            f.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
