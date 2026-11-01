# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A homelab infrastructure-as-code / GitOps repository. There is no runnable web application. It contains:
- Kubernetes manifests reconciled by Flux v2 (`clusters/`)
- Python automation scripts for Proxmox LXC/VM provisioning (`scripts/`, `src/`)
- Docker Compose stacks and Dockerfiles for SDR feeder containers (`compose/`)
- Cloud-init snippets and config templates (`infra/`, `templates/`)

## Dev setup

A `config.ini` file must exist at the repo root — the `Config()` class reads it at module load time, so any code that imports `common.common` fails without it. For `pytest`, the root `conftest.py` auto-copies `scripts/config.ini.example` if no `config.ini` is present. For `python -m unittest`, do the copy manually (`cp scripts/config.ini.example config.ini`).

## Architecture

### Kubernetes (k0s + Cilium + Flux)

- **CNI**: Cilium (eBPF, replaces kube-proxy); Hubble for observability
- **Storage**: Proxmox Ceph accessed via `ceph-csi-rbd`, StorageClass `ceph-rbd`
- **GitOps**: Flux v2 reconciles `clusters/production` and `clusters/edge-sdr` — no local `kubectl apply` workflow
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
