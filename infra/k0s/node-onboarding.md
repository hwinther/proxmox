# k0s node onboarding (Proxmox + cloud-init)

This document describes how to add nodes to an existing k0s cluster after the **VM template** exists (Alpine or Debian + vendor snippets under [`../cloud-init/`](../cloud-init/README.md)). It complements [k0s-multi-node](https://docs.k0sproject.io/stable/k0s-multi-node/) and [remove_controller](https://docs.k0sproject.io/stable/remove_controller/).

Keep **join tokens** and kubeconfig out of Git; use per-VM cloud-init, SSH, or a secret store.

## VM and hostname

1. Clone from the k0s template with per-VM **user** + **network** snippets (see [`../cloud-init/k0s-cloud-init-test.sh`](../cloud-init/k0s-cloud-init-test.sh): `CLONE_VMID`, `CLONE_NAME`, `--network-override`, `--fqdn`).
2. Prefer **`hostname`** (short) + **`fqdn`** (e.g. `k0s-prodNN.k0s.wsh.no`) in user-data so `hostname -f` is correct. **`/etc/hostname`** stays short by default; **Kubernetes node names** follow the kubelet nodename (often the short name) unless you override (see below).
3. On each controller, **`/etc/k0s/k0s.yaml`** must use **this node’s IPs** for:
   - `spec.api.address`
   - `spec.storage.etcd.peerAddress`  
     Duplicating another controller’s IP causes etcd errors such as `Peer URLs already exists`.

## Tokens and roles

| Role                                  | Token                                     | Install command                                                                                                 |
| ------------------------------------- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Worker only**                       | `sudo k0s token create --role worker`     | `sudo k0s install worker --token-file /path/to/worker.token` then `sudo k0s start`                              |
| **Control plane** (new HA member)     | `sudo k0s token create --role controller` | `sudo k0s install controller --token-file /path/to/controller.token -c /etc/k0s/k0s.yaml` then `sudo k0s start` |
| **Control plane + pods on same host** | Controller token                          | Add **`--enable-worker`** to the controller install line                                                        |

Do **not** use `k0s install controller` with a **worker** token, or `k0s install worker` with a **controller** token.

## Control plane + worker on one node

Use a **controller** join token and **`--enable-worker`** so kubelet runs on the controller (pods can schedule subject to taints).

On the **new** VM (after `k0s.yaml` is correct for **this** host):

```bash
sudo k0s install controller \
  --token-file /root/controller.token \
  --enable-worker \
  -c /etc/k0s/k0s.yaml
sudo k0s start
```

Optional:

- **`--no-taints`** — skip default control-plane taints so general workloads schedule without extra tolerations (common in small clusters).
- **`--kubelet-extra-args='--hostname-override=k0s-prodNN.k0s.wsh.no'`** — if you want the **Node** object name to be the FQDN; otherwise kubelet typically uses the short nodename from `/etc/hostname`.

Every HA controller needs its own **`/etc/k0s/k0s.yaml`** consistent with the cluster; see [k0s-multi-node](https://docs.k0sproject.io/stable/k0s-multi-node/#join-controller-node).

## Worker-only node

Workers do **not** use **`/etc/k0s/k0s.yaml`**.

On the new VM:

```bash
sudo k0s install worker --token-file /root/worker.token
sudo k0s start
```

**Networking:** from the worker to **each** controller (or the address embedded in the token): **TCP 6443** (API) and **TCP 8132** (Konnectivity). See [network-plan.md](network-plan.md) and [raspberry-pi-worker.md](raspberry-pi-worker.md) (same join model as VM workers).

**Alpine (OpenRC):** if `k0s start` fails with little output, run **`sudo rc-service k0sworker start`** or **`sudo k0s worker --token-file /root/worker.token`** once in the foreground to capture errors.

**`cilium` CLI on a worker:** it expects a valid **kubeconfig**; workers do not serve the API on `127.0.0.1:8080`. Use `kubectl` / `cilium` from a controller, or copy a kubeconfig from a controller with an appropriate `server:` URL.

## `kubectl` on controllers (`KUBECONFIG`)

On **controller** nodes, k0s stores cluster-admin kubeconfig at:

`/var/lib/k0s/pki/admin.conf`

To use **`kubectl`** (or **`k0s kubectl`**) as root without passing `--kubeconfig` each time, you can add to **`~/.profile`** (or **`~/.bashrc`** on Debian):

```sh
export KUBECONFIG=/var/lib/k0s/pki/admin.conf
```

Notes:

- This file is **cluster-admin**; keep it on trusted controller hosts only.
- **Worker nodes** do not have this path for full admin by default; do not point worker `.profile` at `admin.conf` unless you have deliberately copied it there (not recommended for routine worker roles).

## Taints (control plane + worker)

Controllers often get `node-role.kubernetes.io/control-plane:NoSchedule`. List:

```bash
kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints
```

Remove so workloads can schedule (use the node name shown by `kubectl get nodes`):

```bash
kubectl taint nodes <node-name> node-role.kubernetes.io/control-plane:NoSchedule-
```

New installs can use **`--no-taints`** on **`k0s install controller`** to avoid that taint from the start.

## Removing a controller

Follow [Remove or replace a controller](https://docs.k0sproject.io/stable/remove_controller/) (drain/delete node, etcd leave or `EtcdMember` leave, then `k0s stop` / `k0s reset` on the removed machine). Maintain etcd quorum while doing so.

## Related repo files

- Cluster config shape: [`k0s.yaml.example`](k0s.yaml.example)
- Cilium + API details: [cilium-k0s-setup.md](cilium-k0s-setup.md)
- Cloud-init template / clone helper: [`../cloud-init/README.md`](../cloud-init/README.md), [`../cloud-init/k0s-cloud-init-test.sh`](../cloud-init/k0s-cloud-init-test.sh)
