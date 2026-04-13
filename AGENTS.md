# AGENTS.md

## Cursor Cloud specific instructions

This is a **homelab infrastructure-as-code (IaC) / GitOps repository**. There is no runnable web application in this repo; it contains Kubernetes manifests (Flux-managed), Python automation scripts for Proxmox LXC provisioning, Docker Compose stacks for SDR feeders, and container image Dockerfiles.

### Dev dependencies

- **Python** (>=3.8): runtime dep `dnspython`, dev deps `coverage`, `flake8`, `flake8-html`, `unittest-xml-reporting`, `genbadge[all]`. Install via `pip install dnspython==2.2.1 coverage==7.8.0 unittest-xml-reporting==3.2.0 flake8==7.2.0 flake8-html==0.4.3 "genbadge[all]==1.1.3"`. Note: `pip install -e ".[dev]"` will fail because flit expects a `proxmox` Python module that does not exist; install deps directly instead.
- **Node.js**: only used for `prettier` formatting. Install via `npm install`.

### Running tests

```bash
# Python unit tests (two discovery roots)
python3 -m unittest discover -s src -v
python3 -m unittest discover -s scripts -v

# Coverage (mirrors the npm python-coverage script but without manage.py)
coverage erase && coverage run -m unittest discover -s src && coverage run --append -m unittest discover -s scripts && coverage report
```

A `config.ini` file (copied from `scripts/config.ini.example`) must exist at the repo root for the Python source modules to import successfully (the `Config()` class reads it at module load time).

### Linting

```bash
# Python linting (project uses --exit-zero in CI, warnings are expected)
flake8 --statistics src/ scripts/

# Prettier formatting check (YAML, JSON, Markdown)
npx prettier --check "**/*.{yaml,yml,json,md}"
```

### Kubernetes secrets documentation

When documenting how operators should create credentials for a workload (API tokens, connection strings, etc.), **prefer a Markdown file** in the relevant app directory (for example `pbs-backup-secrets.md`) that lists required keys and gives **`kubectl` CLI examples** (`create secret generic`, `patch`, `describe`). **Do not add committed `Secret` manifests** such as `*.secret.example.yaml` with placeholder `stringData`: they are easy to confuse with real manifests, invite accidental `kubectl apply`, and do not belong in Kustomize `resources`. Link to that doc from Job or Deployment header comments where helpful.

### Key caveats

- The `scripts/example.py` entry point requires a live Proxmox host (calls `pvesh`); it cannot be run locally.
- The `scripts/lsio.py` system-info script queries hardware devices (`nvme`, `/proc/mdstat`, etc.) and will produce empty/error output outside a Proxmox host.
- The Kubernetes manifests are declarative and reconciled by Flux on the actual clusters; there is no local `kubectl apply` workflow.
- SDR Docker images require physical Raspberry Pi + USB SDR hardware to test end-to-end.
