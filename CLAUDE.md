# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A homelab infrastructure-as-code / GitOps repository. There is no runnable web application. It contains:
- Kubernetes manifests reconciled by Flux v2 (`clusters/`)
- Python automation scripts for Proxmox LXC/VM provisioning (`scripts/`, `src/`)
- Docker Compose stacks and Dockerfiles for SDR feeder containers (`compose/`)
- Cloud-init snippets and config templates (`infra/`, `templates/`)

## Dev setup

Build backend is setuptools; `pip install -e ".[dev]"` works from the repo root and pulls in ruff + mypy + pytest + pytest-cov + build:

```bash
pip install -e ".[dev]"
npm install
```

A `config.ini` file must exist at the repo root — the `Config()` class reads it at module load time, so any code that imports `common.common` fails without it. For `pytest`, the root `conftest.py` auto-copies `scripts/config.ini.example` if no `config.ini` is present. For `python -m unittest`, do the copy manually (`cp scripts/config.ini.example config.ini`).

## Commands

```bash
# Run tests (pytest auto-discovers the unittest-style tests under src/ and scripts/)
pytest

# Coverage (pytest-cov uses the [tool.pytest.ini_options] config in pyproject.toml)
pytest --cov=src --cov-report=term

# Lint (ruff — currently configured with select=["E","F","W"], the flake8-equivalent set)
ruff check .

# Format check / apply
ruff format --check .
ruff format .

# Type check
mypy src

# Build smoke (sdist + wheel; matches what the PR workflow runs)
python -m build

# Format check (JSON, Markdown only — YAML is excluded via .prettierignore)
npx prettier --check "**/*.{json,md}"
```

The PR workflow (`.github/workflows/pr-build.yml`) calls the reusable `pr-build.yml` from `hwinther/reusable-workflows`, which runs the same `ruff check` + `ruff format --check` + `mypy src` + `pytest` + `python -m build` pipeline on every PR that touches Python.

## Architecture

### Kubernetes (k0s + Cilium + Flux)

- **CNI**: Cilium (eBPF, replaces kube-proxy); Hubble for observability
- **Storage**: Proxmox Ceph accessed via `ceph-csi-rbd`, StorageClass `ceph-rbd`
- **GitOps**: Flux v2 reconciles `clusters/production` and `clusters/test-deployment` — no local `kubectl apply` workflow
- **Kustomize layout**: `clusters/` references shared bases in `bases/` via relative paths

Namespace convention: `appname-environment` (e.g. `clutterstock-production`, `platform-production`)

Hostname convention:
- Production: `appname.wsh.no`
- Test: `appname.test.wsh.no`
- Management: `*.mgmt.wsh.no`
- Auth (OIDC): `auth.wsh.no`

### Kubernetes secrets

Document operator-created secrets with a Markdown file in the relevant app directory (see `pbs-backup-secrets.md` as example) listing required keys with `kubectl create secret generic` CLI examples. **Do not commit `*.secret.example.yaml`** with placeholder `stringData` — they invite accidental `kubectl apply`.

### Edge / SDR nodes

Two Raspberry Pi ARM64 nodes tainted for SDR-only workloads (`edge-sdr` cluster path). SDR images require physical RPi + USB SDR hardware for end-to-end testing.

### Python automation

`src/` is a modular library for LXC/VM management. `scripts/example.py` and `scripts/lsio.py` require a live Proxmox host (call `pvesh`, query hardware) and will not work locally.

### CI/CD

GitHub Actions (`.github/workflows/`) build and push container images to GHCR, run Flux updates, validate cluster YAML after Dependabot bumps, and prune old images. Releases use `GitVersion.yml` for semver.
