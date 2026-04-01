# Legacy Proxmox template scripts

Cloud-init YAML snippets now live in **[`infra/cloud-init/snippets/`](../../infra/cloud-init/snippets/)** (canonical copy in Git).

On the Proxmox host, symlink `/var/lib/vz/snippets/*.yaml` to that directory (or a checkout path).

**Why Debian failed with `cloud-init-debian-docker.yaml`:** the vendor file used Docker’s **Ubuntu** repository and Ubuntu-only package pins. Use `vendor-docker-debian.yaml` for Debian trixie (13), or `vendor-docker-ubuntu.yaml` for Ubuntu.

When updating `debian.sh`, point `USER_YAML` / `VENDOR_YAML` at the new snippet paths under `infra/cloud-init/snippets/`.

For a **Debian 13 (trixie) + k0s-ready** template (recommended for your cluster nodes), use [`../../infra/cloud-init/create-k0s-debian-template.sh`](../../infra/cloud-init/create-k0s-debian-template.sh) instead of hand-rolling `cicustom`.

For a disposable **test clone** (like `create-debian-cloud-init-test.sh` / `destroy-debian-cloud-init-test.sh` combined), use [`../../infra/cloud-init/k0s-cloud-init-test.sh`](../../infra/cloud-init/k0s-cloud-init-test.sh) (`up`, `up --destroy-first`, `recreate`, `down`, `destroy-all`).
