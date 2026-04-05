# Join a Raspberry Pi as a k0s worker

Short checklist for adding a **worker** node (e.g. Raspberry Pi 3) to an **existing** k0s cluster whose control plane already runs on your LAN (for example Proxmox VMs). This matches the edge pattern in [cluster-architecture-plan.md](../../cluster-architecture-plan.md): `role=sdr-edge` and taint `node-type=edge-sdr:NoSchedule`.

## Prerequisites

- **OS and CPU:** Prefer **64-bit** Raspberry Pi OS so Kubernetes and images line up on **arm64**. A **32-bit** OS needs **armv7** k0s binaries and arm-compatible images; mixed-arch mistakes show up as `Exec format error` or wrong `kubernetes.io/arch` on the node.
- **Time:** Working **NTP** (or systemd-timesyncd) so TLS to the API server succeeds.
- **Disk:** Enough space for container images pulled to `/var/lib/k0s` (k0s kubelet state lives under k0s paths, not `/var/lib/kubelet`).
- **Purpose-built nodes:** If the Pi hosts a USB SDR, confirm on the **host** first (`lsusb`, and a driver-level check such as `rtl_test` or your stack’s equivalent) before expecting in-cluster access.

## Network

From the Pi to **each controller** (or the VIP / address embedded in the join token), allow **outbound**:

| Port | Typical use |
|------|-------------|
| **6443** | Kubernetes API |
| **8132** | Konnectivity (worker agent → server) |

If you use **nodeLocalLoadBalancing** with Envoy (see [cilium-k0s-setup.md](cilium-k0s-setup.md) and [k0s.yaml.example](k0s.yaml.example)), workers still need a working path to the API and Konnectivity endpoints your cluster advertises; align host firewalls with your live `/etc/k0s/k0s.yaml` on controllers.

## Install the worker (same k0s version as controllers)

1. On a controller, create a **worker** join token (set expiry as you prefer):

   ```bash
   sudo k0s token create --role worker
   ```

2. On the Pi, install the **worker** package/binary for **k0s version = controllers** and architecture **arm64** (or **arm** for 32-bit OS).

3. Install and start the worker using the token — follow the [k0s worker documentation](https://docs.k0sproject.io/stable/k0s-multi-node/#join-worker-node) for your exact version (flags differ slightly over time). Typical shape:

   ```bash
   sudo k0s install worker --token-file /path/to/worker.token
   sudo k0s start
   ```

   Alternatively, add the host to **k0sctl** with `role: worker` and the correct `arch` / SSH settings so joins stay repeatable.

4. From your workstation:

   ```bash
   kubectl get nodes -o wide
   ```

   Confirm the node is **Ready**, **ARCH** matches expectations, and **OS** looks correct.

## Label and taint (edge / SDR pool)

Use the same keys as the rest of the repo so [podinfo-edge](../../clusters/production/apps/podinfo-test/podinfo-edge-deployment.yaml) (production k0s cluster, namespace **`podinfo-test`**) and future SDR workloads schedule correctly:

```bash
kubectl label node <pi-hostname> role=sdr-edge --overwrite
kubectl taint nodes <pi-hostname> node-type=edge-sdr:NoSchedule
```

Repeat for each Pi. General workloads without tolerations will not schedule here; edge workloads need the taint **toleration** and **nodeAffinity** (or `nodeSelector`) for `role=sdr-edge`.

## kube-system DaemonSets and the edge taint

Custom **NoSchedule** taints block **every** pod without a matching toleration, including some cluster add-ons.

- **Cilium:** The chart defaults include **`tolerations: [{ operator: Exists }]`**, which tolerates all taints. [k0s.yaml.example](k0s.yaml.example) documents this explicitly so that if you ever **replace** `tolerations` in Helm values, you do not accidentally strand agents off the Pis.
- **konnectivity-agent**, **metrics-server** (k0s stack), **CSI node drivers**, **observability agents**: if any pod stays **Pending** on the Pi with a message about **taints**, add a toleration for `node-type=edge-sdr` (or patch the DaemonSet once and record the change in Git/GitOps). Example patch pattern:

  ```bash
  kubectl -n kube-system get ds
  kubectl describe pod -n kube-system <pending-pod-name>
  ```

  Then patch the owning **DaemonSet** `spec.template.spec.tolerations` to include:

  ```yaml
  - key: node-type
    operator: Equal
    value: edge-sdr
    effect: NoSchedule
  ```

## Ceph CSI on k0s workers

If Pis use **RBD** (or other CSI) volumes, ensure the driver’s node DaemonSet tolerates the edge taint and that values use k0s’s kubelet path **`/var/lib/k0s/kubelet`** — see [README.md](README.md) § Ceph CSI.

## USB / SDR checks (host, then cluster)

1. **On the Pi host:** `lsusb`, correct `/dev` nodes, and a non-Kubernetes smoke test of the radio stack.
2. **In-cluster:** For a disposable check with **hostPath** (e.g. `/dev/bus/usb`), see [usb-sdr-debug-pod.example.yaml](usb-sdr-debug-pod.example.yaml). Longer term, prefer a device plugin such as **smarter-device-manager** (outlined in [cluster-architecture-plan.md](../../cluster-architecture-plan.md)) so workloads request devices instead of raw host paths.
3. **Kyverno:** If [wsh-disallow-host-path](../../bases/kyverno-platform/clusterpolicy-disallow-host-path.yaml) moves to **Enforce** (or you want a clean audit trail), apply a scoped exception — see [kyverno-policyexception-usb-debug.example.yaml](kyverno-policyexception-usb-debug.example.yaml) (example only; tighten labels/namespaces before production use).

## How this differs from `k0s.yaml.example`

[k0s.yaml.example](k0s.yaml.example) is a **controller** `ClusterConfig`: API server, etcd, Konnectivity **server**, Helm-installed Cilium, `nodeLocalLoadBalancing`, pod/service CIDRs, and so on. That file belongs on **controllers**, not copied wholesale to a Pi.

A **worker** only needs the **worker install** and **join token** (plus optional [worker-only config](https://docs.k0sproject.io/stable/worker-node-config/) for kubelet or profiles). Cilium and other extensions are applied **from the control plane**; the Pi runs DaemonSet pods such as **cilium-agent** after it joins.

What must align everywhere: **k0s version**, **kernel** suitability for Cilium, and **network reachability** to the API and Konnectivity path your cluster uses.
