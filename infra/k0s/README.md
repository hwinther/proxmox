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
- Set **Cilium as the CNI** explicitly in k0s configuration (`spec.network.provider: custom`, install Cilium before relying on workers — see **[Cilium + k0s setup guide](cilium-k0s-setup.md)** for API endpoint, CoreDNS, firewalls, and Helm notes). Keep join tokens and sensitive material out of Git (use SOPS/Sealed Secrets for prod secrets).

## 4. Validate networking

- Cilium pods healthy; pod-to-pod and service connectivity; DNS once CoreDNS is running.

## 5. Ceph CSI and StorageClass

- Install CSI to match your Ceph auth and pools; create a **default** or named `StorageClass`(es).
- Validate with a disposable PVC and Pod before application workloads.

## 6. Flux (production path)

- On the **production** cluster only, run Flux bootstrap targeting `./clusters/production` (see [`clusters/production/README.md`](../../clusters/production/README.md)).
- Do not reuse test-cluster `gotk-sync.yaml`; production uses its own `GitRepository` / `Kustomization` pair scoped to `./clusters/production`.

## 7. Applications

- Add platform pieces first (ingress, namespaces, DNS/TLS), then workloads. Use namespaces and secrets separate from test; promote image tags through your CI flow where applicable.
- Name namespaces **`appname-environment`** (always include environment; production-only apps still use e.g. `myapp-production`). Shared stacks: **`platform-<environment>`**. See [`.cursor/skills/flux-gitops/SKILL.md`](../../.cursor/skills/flux-gitops/SKILL.md).
- Public DNS / Ingress: **`appname.wsh.no`** (prod), **`appname.test.wsh.no`** (test), **`appname-<pr>.preview.wsh.no`** (PR previews, e.g. `clutterstock-184.preview.wsh.no`). Same doc.
