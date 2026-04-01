# Proxmox cloud-init snippets (repo copy)

## Why this path

Cloud-init **YAML lives in Git** under `infra/cloud-init/snippets/`. On each Proxmox host, point `cicustom` at **`local:snippets/...`** under `/var/lib/vz/snippets/` (symlink or copy from this repo).

Keeping snippets under **`infra/`** (not `scripts/`) makes it clear these are **infrastructure config** for Proxmox VMs, separate from one-off automation scripts.

## Runtime on Proxmox

1. Copy or symlink files into `/var/lib/vz/snippets/`.
2. Reference them in the VM template:  
   `qm set <vmid> --cicustom "user=local:snippets/<file>.yaml,vendor=local:snippets/<file>.yaml"`
3. Per-clone overrides: regenerate cloud-init or swap vendor data for **join tokens** (avoid baking secrets into the golden template).

### Automated template (Debian 13 / trixie + k0s node vendor)

On the Proxmox host, with this repo checked out (or `SNIPPETS_DIR` pointing at `snippets/`):

```bash
chmod +x infra/cloud-init/create-k0s-debian-template.sh   # from repo root, adjust path
sudo ./infra/cloud-init/create-k0s-debian-template.sh
```

Edit [`snippets/cloud-init-user.example.yaml`](snippets/cloud-init-user.example.yaml) (SSH key, user) **before** cloning the template for production use. Override `VMID`, `STORAGE`, `VMSETTINGS`, `IMAGENAME` / `IMAGEURL` as needed. Set `USE_CUSTOM_USER=0` to use only `scripts/cloud-init/ci-ssh-keys` and vendor data (no `user` snippet).

## Debian vs Ubuntu (Docker snippet)

`vendor-docker-ubuntu.yaml` uses Docker’s **Ubuntu** apt repo. On **Debian**, a vendor file that still points at `download.docker.com/linux/ubuntu` (or pins `~ubuntu...~noble` packages) will fail or behave oddly. Use **`vendor-docker-debian.yaml`** on Debian generic cloud images (`trixie` / Debian 13).

## k0s + Cilium + Ceph CSI

| Layer | Where it runs | Typical mechanism |
|--------|----------------|-------------------|
| **Node OS prep** | First boot | `vendor-k0s-debian-node.yaml` (packages, sysctl, `k0s` binary) |
| **k0s join** | After template clone | `k0s install controller|worker` with token/config (per-clone vendor, Ansible, or SSH) |
| **Cilium** | Cluster exists | Helm or Flux (see [`../k0s/cilium-k0s-setup.md`](../k0s/cilium-k0s-setup.md)) |
| **Ceph CSI** | Cluster exists | Helm or Flux; nodes need kernel **RBD** and **ceph-public** reachability — no CSI Helm in cloud-init |

Do **not** install Cilium or Ceph CSI in cloud-init unless you run a **custom** second-stage with a valid kubeconfig and idempotent Helm — that is brittle for golden templates.

## Related

- Legacy template script: [`../../scripts/cloud-init/debian.sh`](../../scripts/cloud-init/debian.sh) — point `USER_YAML` / `VENDOR_YAML` symlinks at `infra/cloud-init/snippets/` if you want a single source of truth.
- k0s-focused template script: [`create-k0s-debian-template.sh`](create-k0s-debian-template.sh).
- k0s networking + firewall: [`../k0s/network-plan.md`](../k0s/network-plan.md)
