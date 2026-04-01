# k0s with Cilium on Proxmox (homelab guide)

This guide is tailored for a **multi-node** k0s cluster on Proxmox VMs, using **Cilium** as the CNI. It incorporates corrections to common blog examples (API endpoint for workers, CoreDNS, version pinning).

**Official references:**

- [k0s networking (custom CNI)](https://docs.k0sproject.io/stable/networking/)
- [k0s configuration (`spec.network`)](https://docs.k0sproject.io/stable/configuration/#specnetwork)
- [Cilium Helm installation](https://docs.cilium.io/en/stable/installation/k8s-install-helm/)

---

## 1. Plan addresses before installing

| Range | Typical default | Check |
|--------|-----------------|--------|
| **Pod CIDR** | e.g. `10.244.0.0/16` | Must **not** overlap Proxmox LAN, storage networks, or **Ceph public/cluster** subnets |
| **Service CIDR** | e.g. `10.96.0.0/12` | Same as above — unique on your estate |
| **API server** | TCP **6443** on controller(s) | Workers and CLI use this; pick a **stable** target (see §5) |
| **Konnectivity** | TCP **8132** (k0s) | Required worker → controller path per [k0s networking](https://docs.k0sproject.io/stable/networking/) |

Changing CNI **after** the cluster is initialized is effectively a **redeploy** for k0s — choose **`provider: custom`** and Cilium **from day one** if that is your target.

---

## 2. Node prerequisites

- **Linux kernel** meets the **minimum for your Cilium version** (Cilium docs list this per release).
- **No stale CNI config** on workers (`/etc/cni/net.d/` should be managed by whatever installs after k0s — avoid leftovers from old tests).
- **MTU** if you use overlay networking (VXLAN/Geneve): account for overhead on the Proxmox bridge so you do not black-hole large packets.
- **Firewall:** on workers allow **outbound** to controllers: **6443** (Kubernetes API) and **8132** (Konnectivity). Allow traffic involving **pod CIDR** and **service CIDR** as in k0s firewalld examples if you use host firewalls.

---

## 3. k0s `ClusterConfig` outline

Use **`spec.network.provider: custom`** so k0s does not install kube-router. Install **Cilium yourself** (Helm or manifests) once the API server is up.

**Disable kube-proxy only if** you enable **Cilium kube-proxy replacement** for the same k0s/Cilium versions you run — verify in both projects’ docs for your pair.

Example shape (field names **must** match your **k0s version** — open the versioned docs if something fails validation):

```yaml
apiVersion: k0s.k0sproject.io/v1beta1
kind: ClusterConfig
metadata:
  name: k0s
spec:
  network:
    provider: custom
    podCIDR: 10.244.0.0/16      # adjust — no overlap with LAN/Ceph
    serviceCIDR: 10.96.0.0/12   # adjust
    kubeProxy:
      disabled: true            # only with Cilium kube-proxy replacement; else omit/false
```

### CoreDNS

**Do not disable CoreDNS** based on generic “Cilium manages DNS” comments. Cilium is **not** a substitute for **cluster DNS** (CoreDNS). Keep k0s’ normal DNS stack unless you have a **documented** alternative.

---

## 4. Bootstrap order (recommended)

1. **Install and start** the first **controller** with the config above (k0sctl or `k0s install controller --config …`).
2. Obtain **admin kubeconfig** and confirm **API responds** (`kubectl get nodes` may show only controller or NotReady until CNI exists — that can be expected briefly).
3. **Install Cilium** with Helm (or pinned manifests) from a machine with `KUBECONFIG` set.
4. Wait until **Cilium** (and the Cilium **operator**) are **Ready**.
5. **Join workers** with valid tokens; confirm nodes become **Ready**.
6. Run **connectivity checks** (`cilium status`, optional `cilium connectivity test` if CLI installed).

Joining workers **before** Cilium runs can leave nodes without a working pod CNI — prefer **Cilium on the control plane API** as soon as the API is usable, **then** expand workers.

---

## 5. Cilium Helm values that matter (multi-node)

### `k8sServiceHost` / `k8sServicePort`

For **kube-proxy replacement**, Cilium needs the **Kubernetes API** address as seen **from every node** (including **workers**).

| Wrong | Right |
|--------|--------|
| `127.0.0.1` on workers | Workers are not the API server — `127.0.0.1` points at **the wrong host** |

**Use one of:**

- **Stable controller IP** (private LAN) — simplest homelab option  
- **DNS name** resolving to that IP  
- **Load balancer / VIP** for HA control plane (future)  
- **`k8sServiceHostRef`** (Cilium Helm) pointing at a **ConfigMap** that holds host/port, if you automate endpoint discovery — see [Cilium Helm reference](https://docs.cilium.io/en/stable/helm-reference/) for your chart version.

Set **`k8sServicePort`** to **`6443`** unless your install uses a non-default apiserver port.

Avoid assuming **`k8sServiceHost: auto`** works on k0s the same way as on kubeadm clusters unless you confirm what k0s publishes in `kube-public` or similar.

### Other typical knobs

- **`kubeProxyReplacement: true`** only alongside **disabled kube-proxy** in k0s and a **supported** Cilium configuration for your Kubernetes version.
- **`ipam.mode: kubernetes`** aligns with k0s advertising **pod CIDR** to the control plane.
- **Tunnel / datapath** (`tunnel`, `routingMode`, etc.): pick what your Cilium version and kernel support; **VXLAN** is a common default in examples.
- **Small clusters:** `operator.replicas: 1` reduces overhead (not for large HA operator setups).

**Pin** the **Cilium chart version** to a release **tested** with your **exact** k0s (Kubernetes) version.

Example **illustrative** Helm install (replace `<API_HOST>` and chart version):

```bash
helm repo add cilium https://helm.cilium.io/
helm repo update
helm upgrade --install cilium cilium/cilium \
  --namespace kube-system \
  --version <CHART_VERSION> \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost=<API_HOST> \
  --set k8sServicePort=6443 \
  --set ipam.mode=kubernetes \
  --set operator.replicas=1
```

---

## 6. Verify

```bash
kubectl -n kube-system get pods -l k8s-app=cilium
# With Cilium CLI:
cilium status
# Optional full test:
# cilium connectivity test
```

Confirm **DNS**: a short-lived pod that resolves `kubernetes.default` and a `Service` name in your namespace.

---

## 7. After CNI: CSI (Ceph) and GitOps

- **Ceph CSI** is **separate** from this guide: install the driver, pools, secrets, and **`StorageClass`** after pod networking is stable — see the overview in [`README.md`](README.md) §5–7.
- **Flux** can own **Cilium long-term** (HelmRelease) once you are comfortable repeating bootstrap; first cluster install is often **plain Helm** or k0s extensions, then migrate to GitOps if you want.

---

## 8. Third-party articles

Blog posts (e.g. [OneUptime – Configure Cilium on k0s](https://oneuptime.com/blog/post/2026-03-13-configure-cilium-k0s/view)) are useful for **workflow**, but often use **`127.0.0.1`** as `k8sServiceHost` (suitable only on a **single** controller where that matches reality) and may include **misleading CoreDNS commentary**. Prefer **this file** + **k0s/Cilium versioned docs** for values you actually apply.

---

## Checklist

- [ ] `podCIDR` / `serviceCIDR` chosen; no overlap with LAN or Ceph  
- [ ] `provider: custom`; Cilium install procedure ready; versions pinned  
- [ ] `kubeProxy` / `kubeProxyReplacement` aligned for your k0s + Cilium pair  
- [ ] **`k8sServiceHost`** = reachable **control-plane** address from **all** nodes  
- [ ] Firewalls: workers → **6443**, **8132**; pod/service ranges allowed as needed  
- [ ] **CoreDNS** left enabled  
- [ ] Cilium **Ready**; basic pod + **DNS** check passed  
- [ ] Then: Ceph CSI, then workloads / Flux  
