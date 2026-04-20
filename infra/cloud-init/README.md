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

### Automated template (Alpine generic cloud + k0s node vendor)

Same flow as Debian, but the vendor snippet uses **apk** packages and **OpenRC** (`vendor-k0s-alpine-node.yaml`). It follows the [k0s-on-Alpine host prep checklist](https://blog.devdemand.co/deploying-k0s-alpine/) (cgroups v2 unified, dbus, udev), adds **`rshared` on the root mount** in `/etc/fstab` plus `mount -o remount,rshared /` for **Cilium** (Alpine 3.20+ pattern), omits the article’s sysfs eBPF edit, and ends with **one automatic reboot** after first-boot provisioning so `rc_cgroup_mode` matches the guide. Default image is a pinned **BIOS** `qcow2` from [Alpine’s cloud index](https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/cloud/) (`generic_alpine-*-x86_64-bios-cloudinit-r0.qcow2`). Bump `IMAGENAME` when Alpine publishes a newer generic build; use a **UEFI** `*-uefi-cloudinit-*.qcow2` if the VM uses OVMF.

```bash
chmod +x infra/cloud-init/create-k0s-alpine-template.sh
sudo ./infra/cloud-init/create-k0s-alpine-template.sh
```

Default template **VMID is 10011** (Debian k0s template defaults to **10010**) so both can coexist. [`k0s-cloud-init-test.sh`](k0s-cloud-init-test.sh) still points at the Debian creator by default; point **`CREATE_TEMPLATE_SCRIPT`** at `create-k0s-alpine-template.sh` and set **`TEMPLATE_VMID`** to match when testing Alpine clones.

### Static network (`NETWORK_SOURCE`)

Example cloud-init **network v1** (static IPv4 + nameservers), same shape as `qm cloudinit dump <vmid> network`:

- [`snippets/network-example-static.yaml`](snippets/network-example-static.yaml)

Edit a copy (or the example) in the repo, then run the template script on the Proxmox host with **`NETWORK_SOURCE`** pointing at that file — the script symlinks it into `/var/lib/vz/snippets/` like user/vendor data:

```bash
NETWORK_SOURCE="${PWD}/infra/cloud-init/snippets/network-example-static.yaml" \
  sudo ./infra/cloud-init/create-k0s-debian-template.sh
```

Optional: **`NETWORK_SNIPPET_NAME=my-net.yaml`** if the filename under `snippets/` should differ from the source basename. When `NETWORK_SOURCE` is unset, the script sets **`ipconfig0` DHCP** (no custom network in `cicustom`).

### Test clone (single script)

[`k0s-cloud-init-test.sh`](k0s-cloud-init-test.sh) replaces a separate create/destroy pair: it clones the k0s template to a disposable VM (default **20010** from **10010**), starts it, and opens `qm terminal` unless `NO_TERMINAL=1`.

```bash
sudo ./infra/cloud-init/k0s-cloud-init-test.sh up              # create template if missing, clone, start, console
sudo ./infra/cloud-init/k0s-cloud-init-test.sh up --destroy-first   # drop existing clone first
DESTROY_FIRST=1 sudo ./infra/cloud-init/k0s-cloud-init-test.sh up   # same as --destroy-first
sudo ./infra/cloud-init/k0s-cloud-init-test.sh recreate        # down + up (fresh clone)
sudo ./infra/cloud-init/k0s-cloud-init-test.sh down            # destroy clone only (keep template)
sudo ./infra/cloud-init/k0s-cloud-init-test.sh destroy-all     # destroy clone + template
sudo ./infra/cloud-init/k0s-cloud-init-test.sh template        # run create-k0s-debian-template.sh only
```

Override **`TEMPLATE_VMID`**, **`CLONE_VMID`**, **`CLONE_NAME`** as needed.

**Two NICs (k0s node + ceph-public):** use [`snippets/network-example-static-dual-nic.yaml`](snippets/network-example-static-dual-nic.yaml). It sets a static address on each interface and **omits a gateway on the ceph-public NIC** so default routing stays on the cluster/management side, matching a firewall layout where ceph-public has no internet egress. In Proxmox, add **`net1`** (second virtio + correct bridge/VLAN) to the template or clone; align interface names and MACs in the YAML with `qm config <vmid>`.

## Debian vs Ubuntu (Docker snippet)

`vendor-docker-ubuntu.yaml` uses Docker’s **Ubuntu** apt repo. On **Debian**, a vendor file that still points at `download.docker.com/linux/ubuntu` (or pins `~ubuntu...~noble` packages) will fail or behave oddly. Use **`vendor-docker-debian.yaml`** on Debian generic cloud images (`trixie` / Debian 13).

## k0s + Cilium + Ceph CSI

| Layer            | Where it runs        | Typical mechanism                                                                                    |
| ---------------- | -------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **Node OS prep** | First boot           | `vendor-k0s-debian-node.yaml` or `vendor-k0s-alpine-node.yaml` (packages, sysctl, `k0s` binary)      |
| **k0s join**     | After template clone | `k0s install controller                                                                              | worker` with token/config (per-clone vendor, Ansible, or SSH) |
| **Cilium**       | Cluster exists       | Helm or Flux (see [`../k0s/cilium-k0s-setup.md`](../k0s/cilium-k0s-setup.md))                        |
| **Ceph CSI**     | Cluster exists       | Helm or Flux; nodes need kernel **RBD** and **ceph-public** reachability — no CSI Helm in cloud-init |

Do **not** install Cilium or Ceph CSI in cloud-init unless you run a **custom** second-stage with a valid kubeconfig and idempotent Helm — that is brittle for golden templates.

## Related

- Legacy template script: [`../../scripts/cloud-init/debian.sh`](../../scripts/cloud-init/debian.sh) — point `USER_YAML` / `VENDOR_YAML` symlinks at `infra/cloud-init/snippets/` if you want a single source of truth.
- k0s-focused template scripts: [`create-k0s-debian-template.sh`](create-k0s-debian-template.sh), [`create-k0s-alpine-template.sh`](create-k0s-alpine-template.sh).
- k0s networking + firewall: [`../k0s/network-plan.md`](../k0s/network-plan.md)
