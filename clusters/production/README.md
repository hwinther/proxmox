# Production cluster (k0s)

GitOps manifests for the production cluster. Flux on **this** cluster must sync **only** `./clusters/production`, never `./clusters/test-deployment`.

## First-time Flux bootstrap

Run from a machine with `flux` CLI and GitHub credentials (replace owner/repo/branch if needed):

```bash
flux bootstrap github \
  --token-auth \
  --components-extra=image-reflector-controller,image-automation-controller \
  --owner=hwinther \
  --repository=proxmox \
  --branch=main \
  --path=clusters/production \
  --read-write-key \
  --personal
```

If this directory and `flux-system` already exist in Git, bootstrap reconciles against the committed `gotk-sync.yaml` and `gotk-components.yaml`. After upgrading Flux versions, regenerate `flux-system/gotk-components.yaml` (for example via `flux install --export`) and align with [`../test-deployment/flux-system/gotk-components.yaml`](../test-deployment/flux-system/gotk-components.yaml) when both clusters should run the same controller version.

## In-cluster sync

[`flux-system/gotk-sync.yaml`](flux-system/gotk-sync.yaml) defines a `GitRepository`, **`clutterstock-migrate`** and **`clutterstock-test-migrate`** `Kustomization`s (paths under `apps/clutterstock*-migrate/`), and the root **`flux-system`** `Kustomization` with `path: ./clusters/production`. The root **`flux-system` Kustomization does not `dependsOn` migrate**: if migrate were blocked (PVC not bound, missing `csi-rbd-secret`, etc.), that would prevent **all** of production (including observability) from applying. Run the migrator Job and wait for success before relying on each Clutterstock API if you need a strict DB migration order.

Platform checklist before apps: [`../../infra/k0s/README.md`](../../infra/k0s/README.md). **Ceph RBD:** Flux manifests under [`apps/ceph-csi/`](apps/ceph-csi/README.md) (fill in FSID/monitors, create `csi-rbd-secret` before expecting PVCs).

### Troubleshooting: empty namespace / no HelmReleases

1. **Git:** Flux reads **`main`** on `https://github.com/hwinther/proxmox.git`. Local-only commits are invisible until **pushed**.
2. **Reconcile:** `flux reconcile source git flux-system -n flux-system` then `flux reconcile kustomization flux-system -n flux-system`.
3. **Status:** `flux get kustomizations -n flux-system` — if `flux-system` is **NotReady**, read `kubectl describe kustomization flux-system -n flux-system` (kustomize build errors, denied RBAC, etc.).
4. **Migrate KS:** `flux get kustomization clutterstock-migrate -n flux-system` (and **`clutterstock-test-migrate`**) — failing migrate does **not** block the root bundle anymore; fix PVC/Job for the matching Clutterstock stack all the same.
5. **Kyverno / `No agent available`:** Workload webhooks and **ClusterPolicy** webhooks both call the Kyverno **Service** from the apiserver. **`forceFailurePolicyIgnore`** (see `apps/kyverno/kyverno-helmrelease.yaml`) does **not** relax **`mutate-policy.kyverno.svc`** (Flux **`kyverno-policies`** dry-run). Fix **Konnectivity (8132)** and **Service VIP from controllers** per [`infra/k0s/cilium-k0s-setup.md`](../../infra/k0s/cilium-k0s-setup.md). If **`kyverno`** shows an older Git **revision** than **`flux-system`**, run `flux reconcile kustomization kyverno -n flux-system --with-source` so the admission controller chart values (including that flag) match Git.

## Apps on this cluster

| Area | Path | Notes |
|------|------|--------|
| **Observability** | [`apps/observability/`](apps/observability/) | kube-prometheus-stack, Loki, Tempo, OTel; see [README](apps/observability/README.md) |
| **Traefik** | [`apps/traefik/`](apps/traefik/) | DaemonSet + hostNetwork (same pattern as test) |
| **Homepage** | [`apps/homepage/`](apps/homepage/) | Namespace `platform-production`; Ingress host **`mgmt.wsh.no`** |
| **Shared (env-scoped)** | [`apps/shared/`](apps/shared/) | **`shared-production`** / **`shared-test`** — Redis (etc.) shared per environment line; see [README](apps/shared/README.md) |
| **Clutterstock** | [`apps/clutterstock/`](apps/clutterstock/) | Namespace `clutterstock-production`, Ceph PVC via migrate; Redis → **`shared-production`**; public **`clutterstock.wsh.no`** |
| **Clutterstock (test)** | [`apps/clutterstock-test/`](apps/clutterstock-test/) | Namespace **`clutterstock-test`**, separate SQLite PVC + [`clutterstock-test-migrate/`](apps/clutterstock-test-migrate/); Redis → **`shared-test`**; **`clutterstock.test.wsh.no`** for Playwright / release validation |
| **Podinfo (edge / Pi)** | [`apps/podinfo-test/`](apps/podinfo-test/) | Namespace **`podinfo-test`** (not **`test-test`**); **`podinfo-edge.test.wsh.no`** — scheduling demo for SDR edge nodes; see [README](apps/podinfo-test/README.md) |
| **Test (sample app)** | [`apps/test-test/`](apps/test-test/) | Namespace **`test-test`** (app **test** + env **test**); **`test.test.wsh.no`** (UI + `/api`, same images as test-deployment cluster) |
| **Policy Reporter** | [`apps/policy-reporter-production/`](apps/policy-reporter-production/) | Kyverno policy reports UI; **`policy-reporter.mgmt.wsh.no`** |
| **Ingress** | [`apps/ingress.yaml`](apps/ingress.yaml) | Public + management hosts (see hostnames below) |

## Namespace naming

Follow **`appname-environment`** (lowercase, hyphens): include the environment in every app namespace, including production-only workloads (e.g. `clutterstock-api-production`). Use **`platform-production`** (or `platform-<env>`) for shared platform namespaces. Details: [`.cursor/skills/flux-gitops/SKILL.md`](../../.cursor/skills/flux-gitops/SKILL.md).

The placeholder namespace under `apps/` is `platform-production` for cluster-wide GitOps-owned resources until real apps add their own `*-namespace.yaml` files.

## Public hostnames (`wsh.no`)

- **Applications:** **`{service}.wsh.no`** — e.g. `clutterstock.wsh.no` (Clutterstock API is routed on the same host under `/api/`). Non-prod Clutterstock on this cluster: **`clutterstock.test.wsh.no`** (see table above).
- **Management plane:** **Homepage** uses **`mgmt.wsh.no`**. Other management UIs use **`{service}.mgmt.wsh.no`** — e.g. `grafana.mgmt.wsh.no`, `otel.mgmt.wsh.no`, `alertmanager.mgmt.wsh.no`, **`policy-reporter.mgmt.wsh.no`** (Kyverno reports via [Policy Reporter UI](https://kyverno.github.io/policy-reporter-docs/policy-reporter-ui/introduction.html)), **`redis-prod.mgmt.wsh.no`** / **`redis-test.mgmt.wsh.no`** (RedisInsight for **`shared-production`** / **`shared-test`** Redis). Prefer stricter edge controls (WAF / auth) on `mgmt.wsh.no` and `*.mgmt.wsh.no`.

Non-prod uses **`appname.test.wsh.no`** or test-specific zones (e.g. `*.kt.wsh.no`); PR previews use **`appname-<pr-number>.preview.wsh.no`**. The **`test.test.wsh.no`** hostname is the sample **`ghcr.io/hwinther/test`** stack: **test-environment** traffic (`*.test.wsh.no`), not “production product” traffic, even though the workload runs on this cluster (see [`apps/test-test/README.md`](apps/test-test/README.md)). See [`.cursor/skills/flux-gitops/SKILL.md`](../../.cursor/skills/flux-gitops/SKILL.md).
