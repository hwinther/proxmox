# Join a Raspberry Pi as a k0s worker

Short checklist for adding a **worker** node (e.g. Raspberry Pi 3) to an **existing** k0s cluster whose control plane already runs on your LAN (for example Proxmox VMs). This matches the edge pattern in [cluster-architecture-plan.md](../../cluster-architecture-plan.md): `role=sdr-edge` and taint `node-type=edge-sdr:NoSchedule`.

If the cluster uses k0s **`nodeLocalLoadBalancing`**, each worker runs an **NLLB (Envoy)** static pod. On a **Pi 3 with ~1 GiB RAM**, that Envoy process may **OOM / mmap-fail** and never bind **7443** — see § **Raspberry Pi 3 and `nodeLocalLoadBalancing`**.

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

## Which API server is the worker using?

There are two practical places to look:

### 1. **`/var/lib/k0s/kubelet/kubeconfig` missing**

That path (or similar) is usually created **after** the worker has **successfully** bootstrapped against the API. If join kept failing, the directory may be empty or only hold partial state — **`No such file or directory` is normal until the worker comes up cleanly.**

Still useful on a **healthy** worker:

```bash
sudo grep -R 'server: https://' /var/lib/k0s/kubelet/ 2>/dev/null
sudo find /var/lib/k0s -type f \( -name 'kubeconfig' -o -name '*.conf' \) 2>/dev/null
```

### 2. **Decode the join token (works before kubelet has a config)**

The public docs describe the token as “base64-encoded kubeconfig”; in k0s itself the pipeline is **`base64` → `gzip` → kubeconfig YAML** (see `DecodeJoinToken` in k0s [`pkg/token/joindecode.go`](https://github.com/k0sproject/k0s/blob/main/pkg/token/joindecode.go)). So **`base64 -d` alone looks like random binary** — that blob is **compressed**. You must **gunzip** (or decompress in Python) to see `server:`.

On the Pi, use the same file you passed to **`k0s install worker --token-file`** (commonly **`/var/lib/k0s/join-token`**):

```bash
sudo wc -c /var/lib/k0s/join-token
sudo tr -d '\n\r' < /var/lib/k0s/join-token | base64 -d | gunzip -c | grep -i 'server:'
```

Peek kubeconfig after decompress:

```bash
sudo tr -d '\n\r' < /var/lib/k0s/join-token | base64 -d | gunzip -c | head -25
```

The **`server:`** line is the API URL this worker uses (must be reachable from the Pi, e.g. **`nc -zv … 6443`**).

Portable fallback (base64 **standard** encoding + gzip; needs Python 3):

```bash
sudo python3 <<'PY'
import base64, gzip, io, pathlib, sys
raw = pathlib.Path("/var/lib/k0s/join-token").read_bytes().replace(b"\n", b"").replace(b"\r", b"")
try:
    gz = base64.standard_b64decode(raw)
    text = gzip.decompress(gz).decode("utf-8")
except Exception as e:
    print("decode failed:", e, file=sys.stderr)
    sys.exit(1)
for line in text.splitlines():
    if "server:" in line.lower():
        print(line.strip())
PY
```

If **`gunzip` / Python still fail**, the file may be corrupted or not raw `k0s token create` output — mint a new token on the controller and reinstall / replace **`/var/lib/k0s/join-token`**. **`wc -c` is 0** means nothing was written.

**Rare:** if someone saved **plain YAML** kubeconfig into the file (no base64/gzip), **`grep -i server /var/lib/k0s/join-token`** works without decoding.

**On the controller**, that URL should align with **`spec.api.address`** (and port **`6443`** unless customized) in `/etc/k0s/k0s.yaml`, or your VIP / LB fronting the API.

## Troubleshooting worker bootstrap (`timed out waiting to connect to apiserver`)

If **`k0sworker.service`** logs **`Error waiting for apiserver to come up`** / **`failed to bootstrap kubelet client configuration`**, the Pi never established **TCP + TLS** to the **Kubernetes API** URL inside the **join token** (before Konnectivity is fully in play).

Work in order:

1. **Do not put a controller `ClusterConfig` on the worker** (`spec.api`, `spec.storage.etcd`, `extensions.helm`, …). Use **worker install + token** only (see § “How this differs from `k0s.yaml.example`”). A copied controller file does not fix API reachability and can muddy role expectations.
2. **Confirm the API URL the worker will use** (must be an IP/DNS the Pi can route to — almost always a controller **LAN** address on **6443**, never `127.0.0.1` on the Pi). It is embedded in the **join token**; if unsure, mint a new token on a working controller and compare with your controllers’ **`spec.api.address`** / VIP. Re-run **`k0s install worker`** with the updated token per [k0s worker docs](https://docs.k0sproject.io/stable/k0s-multi-node/#join-worker-node).

3. **From the Pi**, prove Layer 3 + port (replace with the **same host** the token advertises, often **`spec.api.address`** on a controller):

   ```bash
   ping -c 2 <controller-ip-or-dns>
   nc -zv <controller-ip-or-dns> 6443
   nc -zv <controller-ip-or-dns> 8132
   ```

   - **`6443` timeout:** controller firewall, wrong subnet/VLAN, wrong IP in token, or apiserver not listening on that interface (bind address).
   - **`8132` timeout:** Konnectivity will fail later; fix reachability to controllers for **8132** as in the [Network](#network) table. See also [`cilium-k0s-setup.md`](cilium-k0s-setup.md) if you use **nodeLocalLoadBalancing** / HA.

4. **Clock skew:** TLS handshakes fail mysteriously if time is off — `timedatectl status` on the Pi and controllers.

5. **k0s version** on the Pi must **match** the cluster’s controllers (worker–controller mismatch can show up as odd bootstrap failures).

### After join: kubelet errors on `https://[::1]:7443` (`connection refused`)

With **`nodeLocalLoadBalancing`** (Envoy on each node), k0s usually switches the **kubelet** API client to the **node-local proxy** on port **7443** (see [k0s.yaml.example](k0s.yaml.example)). Logs may show:

`Unable to register node with API server` … `dial tcp [::1]:7443: connect: connection refused`

**What it means:** kubelet expects the **node-local Envoy** (NLLB) on **7443**. **`connection refused`** means nothing is accepting that port (often **`[::1]:7443`** if kubelet prefers IPv6, while Envoy listens only on **`127.0.0.1:7443`** — two different failure shapes).

**`crictl` on the Pi:** install **`cri-tools`** if needed (Debian / Raspberry Pi OS: **`apt-get install -y cri-tools`**). k0s’s CRI socket is usually **`unix:///run/k0s/containerd.sock`** (confirm with **`find /run -name containerd.sock`** — do **not** assume **`/run/containerd/containerd.sock`**, that path is often missing on workers).

Persist endpoints (stops default-socket spam and failures):

```bash
sudo tee /etc/crictl.yaml <<'EOF'
runtime-endpoint: unix:///run/k0s/containerd.sock
image-endpoint: unix:///run/k0s/containerd.sock
EOF
```

**crictl v1.30+:** the **`pods`** subcommand has **no** **`-a`** flag. List sandboxes with **`crictl pods`** (optional **`--name nllb-radio-pi02`**), and containers with **`crictl ps --all`** (note **`--all`**, not only **`-a`**, depending on version — if **`-a`** errors, use long form).

```bash
sudo crictl pods | grep -i nllb
sudo crictl ps --all | grep -i nllb
sudo crictl logs <nllb-container-id>
```

Without **`crictl`**, **containerd** **`ctr`** uses the same socket:

```bash
sudo ctr --address /run/k0s/containerd.sock -n k8s.io containers list | grep -i nllb
```

### Raspberry Pi 3 (≈1 GiB RAM) and **`nodeLocalLoadBalancing`** (NLLB / Envoy)

On a **memory-tight** Pi, the **NLLB** container (**`nllb-<hostname>`**) may **exit immediately**. **`crictl logs`** then shows **TCMalloc** / **`mmap`** failures (large aligned allocations) or OOM — Envoy does not open **7443**, so kubelet cannot register (`[::1]:7443` **connection refused**).

**Options:**

1. **Hardware / RAM:** prefer a **Pi 4/5 with more RAM** if you must keep cluster-wide **`nodeLocalLoadBalancing`** (see [k0s.yaml.example](k0s.yaml.example) and [cilium-k0s-setup.md](cilium-k0s-setup.md)).
2. **Cluster config:** disabling **`nodeLocalLoadBalancing`** is a **control-plane** change with **HA / Konnectivity** tradeoffs — only after reading **`cilium-k0s-setup.md`** (Envoy, **7443** / **7132**, multi-controller behavior) and planning a maintenance window.
3. **Upstream:** watch for k0s issues or knobs for lighter NLLB on edge nodes.

There is usually **no per-node “skip NLLB”** flag: if the cluster enables it, **every** node is expected to run the static pod.

**On the worker, check:**

```bash
sudo ss -tlnp | grep 7443 || echo "nothing on 7443"
curl -gk --max-time 3 https://127.0.0.1:7443/version || true
curl -gk --max-time 3 https://[::1]:7443/version || true
```

- **`netstat` / `ss` shows no `7443` at all** (only ssh, kubelet **10250**, k0s internal ports, etc.): **Envoy never started listening** — the **NLLB** static pod is not Running, is crash-looping, or never got applied. That blocks node registration until it is fixed.
  - Inspect containers: **`sudo crictl ps --all`** (with **`/etc/crictl.yaml`** or env endpoints above), then **`sudo crictl logs <nllb-container-id>`**.
  - Find manifests under **`/var/lib/k0s`** (paths vary by version), e.g. **`grep -r nllb /var/lib/k0s --include='*.yaml' 2>/dev/null`**.
  - **Memory / Envoy:** see **§ Raspberry Pi 3 and `nodeLocalLoadBalancing`** above; also **`dmesg | grep -i oom`**, **`free -h`**, **`sudo crictl images`**
- If **127.0.0.1:7443** works but **`[::1]:7443`** does not, that is the **IPv4-only listener** case: mitigations include **k0s**/OS updates, or **disabling IPv6** on the node (last resort) so `localhost` resolves to IPv4 only.
- After fixing NLLB, **`sudo systemctl restart k0sworker`** once **`ss`** shows **`7443`** listening; confirm **`kubectl get node <hostname>`** from the cluster.

This is separate from **6443** to the controller (your join-token **`server:`**): that path can work while **post-bootstrap** kubelet still targets **7443** locally.

## Label and taint (edge / SDR pool)

Use the same keys as the rest of the repo so [podinfo-edge](../../clusters/edge-sdr/apps/podinfo-edge-sdr/podinfo-edge-deployment.yaml) (edge-sdr cluster, namespace **`podinfo-edge-sdr`**) and future SDR workloads schedule correctly:

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
