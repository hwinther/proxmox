# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A homelab infrastructure-as-code / GitOps repository. There is no runnable web application. It contains:
- Kubernetes manifests reconciled by Flux v2 (`clusters/`)
- Python automation scripts for Proxmox LXC/VM provisioning (`scripts/`, `src/`)
- Docker Compose stacks and Dockerfiles for SDR feeder containers (`compose/`)
- Cloud-init snippets and config templates (`infra/`, `templates/`)

## Dev setup

**Do not run `pip install -e ".[dev]"`** — flit expects a `proxmox` Python module that doesn't exist. Install deps directly:

```bash
pip install dnspython==2.2.1 coverage==7.8.0 unittest-xml-reporting==3.2.0 flake8==7.2.0 flake8-html==0.4.3 "genbadge[all]==1.1.3"
npm install
```

A `config.ini` file must exist at the repo root (copy from `scripts/config.ini.example`) — the `Config()` class reads it at module load time, so tests fail without it.

## Commands

```bash
# Run tests
python3 -m unittest discover -s src -v
python3 -m unittest discover -s scripts -v

# Coverage
coverage erase && coverage run -m unittest discover -s src && coverage run --append -m unittest discover -s scripts && coverage report

# Python linting (--exit-zero: warnings expected)
flake8 --statistics src/ scripts/

# Format check (JSON, Markdown only — YAML is excluded via .prettierignore)
npx prettier --check "**/*.{json,md}"
```

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
