# k0s on Proxmox (production baseline)

Follow this order on lab nodes before relying on the same steps in production. Adjust for your Ceph topology (RBD, CephFS, or both) and k0s/Cilium release notes.

## 1. Proxmox and Ceph

- Ensure the Ceph cluster is healthy (`ceph status`), pools exist for Kubernetes, and public/cluster networks match how VM nodes reach OSDs and each other.
- Decide **RBD vs CephFS** (or both) for PVCs; install the matching **Ceph CSI** driver and `StorageClass` after Kubernetes API is available (step 5).
- Use the concrete VLAN/CIDR and firewall baseline in **[network-plan.md](network-plan.md)**.

## 2. Node OS (Cilium prerequisites)

Per node VM: kernel and modules required by your Cilium version, sysctl/conntrack tuning as documented by Cilium, correct MTU if using encapsulation, and **no leftover CNI** from other installers. Debian cloud-init baseline for nodes: [`../cloud-init/snippets/vendor-k0s-debian-node.yaml`](../cloud-init/snippets/vendor-k0s-debian-node.yaml) (see [`../cloud-init/README.md`](../cloud-init/README.md)).

Confirm **k0s + Cilium** compatibility for your chosen versions (CNI-only vs kube-proxy replacement).

## 3. Bootstrap k0s

- Use `k0sctl` or your standard method; keep **repeatable config** (API addresses, control-plane and worker roles, worker profiles).
- **Cilium + Hubble Helm values** under `spec.extensions.helm.charts` should include **`cluster.name`**, **`hubble`** (relay + TLS auto + `peerService.internalTrafficPolicy: Cluster`), and a **pinned chart `version`** — see [`k0s.yaml.example`](k0s.yaml.example) (generic IPs) or [`k0s.production.example.yaml`](k0s.production.example.yaml) (shape matching the production LAN). Merge into `/etc/k0s/k0s.yaml` on controllers so k0s does not run “minimal” Cilium without Hubble.
- Set **Cilium as the CNI** explicitly in k0s configuration (`spec.network.provider: custom`, install Cilium before relying on workers — see **[Cilium + k0s setup guide](cilium-k0s-setup.md)** for API endpoint, CoreDNS, firewalls, and Helm notes). Keep join tokens and sensitive material out of Git (use SOPS/Sealed Secrets for prod secrets).

## 4. Validate networking

- Cilium pods healthy; pod-to-pod and service connectivity; DNS once CoreDNS is running.

### metrics-server (k0s default)

k0s installs **metrics-server** in `kube-system` (static stack `metricserver`). It satisfies `metrics.k8s.io` for `kubectl top`, HPAs, and tools like Homepage’s kubernetes widget.

- **Do not** add a second metrics-server with Helm/Flux unless you first **disable** the built-in one, e.g. controller install flag [`--disable-components=metrics-server`](https://docs.k0sproject.io/stable/configuration/) (same entry appears in k0s docs under component toggles). Otherwise expect name collisions or failed Helm adoption.
- **Tuning:** The stock manifest already uses `--kubelet-use-node-status-port` and preferred address types. Add **`--kubelet-insecure-tls`** only when logs show **certificate** verification errors against the kubelet, not for generic “connection refused” (that usually means kubelet/firewall/path—see [cilium-k0s-setup.md](cilium-k0s-setup.md)). To change args on the k0s-managed Deployment, patch in place or switch to GitOps-owned metrics-server after disabling the k0s component.
- **Health:** `kubectl get apiservice v1beta1.metrics.k8s.io` should show `AVAILABLE=True`; `kubectl top nodes` should list all nodes. Brief `FailedDiscoveryCheck` during joins or overload can clear once scrapes succeed again.

## 5. Ceph CSI and StorageClass

- **Production (GitOps):** Flux deploys **ceph-csi-rbd** from [`clusters/production/apps/ceph-csi/`](../../clusters/production/apps/ceph-csi/README.md) (namespace `ceph-csi-production`, StorageClass `ceph-rbd`). Set **`kubeletDir: /var/lib/k0s/kubelet`** there — k0s does not use `/var/lib/kubelet`.
- **Manual / other clusters:** Install CSI to match your Ceph auth and pools; create a **default** or named `StorageClass`(es).
- Validate with a disposable PVC and Pod before application workloads.

## 6. Flux (production path)

- On the **production** cluster only, run Flux bootstrap targeting `./clusters/production` (see [`clusters/production/README.md`](../../clusters/production/README.md)).
- Do not reuse test-cluster `gotk-sync.yaml`; production uses its own `GitRepository` / `Kustomization` pair scoped to `./clusters/production`.

## 7. Applications

- Add platform pieces first (ingress, namespaces, DNS/TLS), then workloads. Use namespaces and secrets separate from test; promote image tags through your CI flow where applicable.
- Name namespaces **`appname-environment`** (always include environment; production-only apps still use e.g. `myapp-production`). Shared stacks: **`platform-<environment>`**. See [`.cursor/skills/flux-gitops/SKILL.md`](../../.cursor/skills/flux-gitops/SKILL.md).
- Public DNS / Ingress: **`appname.wsh.no`** (prod), **`appname.test.wsh.no`** (test), **`appname-<pr>.preview.wsh.no`** (PR previews, e.g. `clutterstock-184.preview.wsh.no`). Same doc.
