# Kube DOOM (chaos toy)

Play id's **DOOM** where every monster on the map is a **live pod** in this cluster; kill a monster
and kubedoom runs `kubectl delete pod` on the real thing. Browser access via noVNC behind Authelia.

> ⚠️ **Cluster-wide.** The bound ClusterRole (`rbac.yaml`) grants `pods: get/list/delete` across
> **all namespaces**. A stray rocket really will delete a production pod (Postgres, Authelia,
> CNPG, …). Kubernetes/CNPG will reschedule, but treat this as a live-fire chaos tool, not a demo.
> It is deliberately **not** `cluster-admin` (the upstream default) — pods are all it can touch.

## Dormant by default

`kubedoom-deployment.yaml` ships **`replicas: 0`** — nothing runs until you start a session. Flux
owns the replica count, so a manual `kubectl scale` is reverted on the next reconcile.

**To play:**

```bash
# Option A (GitOps): set replicas: 1 in kubedoom-deployment.yaml, commit, let Flux apply.
# Option B (quick session): suspend reconcile, scale up by hand, then undo when done.
flux suspend kustomization apps -n flux-system
kubectl -n kubedoom scale deploy/kubedoom --replicas=1
# ... play at https://doom.mgmt.wsh.no ...
kubectl -n kubedoom scale deploy/kubedoom --replicas=0
flux resume kustomization apps -n flux-system
```

## Access & controls

- URL: **https://doom.mgmt.wsh.no** (Authelia-gated; the mgmt path skips NAXSI, so Authelia is the
  only gate — keep its access tight).
- The browser will prompt for the **VNC password: `idbehold`** (a DOOM cheat code).
- Use `idspispopd` (noclip) in-game to walk through walls to the monsters/pods.
- **CTRL** fires. Each monster is named for the pod it represents; killing it deletes that pod.
- Scope: no `NAMESPACE` env is set, so monsters are **every pod cluster-wide**. To limit the blast
  radius, add `env: [{name: NAMESPACE, value: <ns>}]` to the kubedoom container — then only that
  namespace's pods appear.

## How it's wired (mirrors `headlamp-production`)

- `rbac.yaml` — SA + minimal cluster-wide `pods` ClusterRole + binding (not cluster-admin).
- `kubedoom-deployment.yaml` — kubedoom (DOOM/dosbox/x11vnc on :5900) + `novnc` sidecar bridging
  to a web port (:6080); ClusterIP Service `:80 -> 6080`.
- `kubedoom-ingress.yaml` — `doom.mgmt.wsh.no` via Traefik + Authelia forwardauth.
- `networkpolicies.yaml` + `cilium-cluster-nodes-to-http.yaml` — default-deny floor
  (netpol-baseline component) + Traefik→6080 ingress + egress to the apiserver only.
- `kyverno-policyexception-kubedoom.yaml` — accepts the (Audit-only) run-as-non-root finding;
  dosbox/x11vnc need root.

## Images

- `ghcr.io/storax/kubedoom:0.6.0` (third-party; semver tag, Dependabot-trackable).
- `ghcr.io/wavyland/novnc@sha256:45b5c470…` — pinned by digest because upstream publishes
  **latest only** (no semver), per the compliance SKILL's latest-only path.
