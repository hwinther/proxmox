---
name: flux-gitops
description: >-
  Manage the Flux GitOps workflow for the Kubernetes cluster in this repo.
  Use when adding, removing, or updating apps synced by Flux, working with
  Kustomization resources, or troubleshooting Flux reconciliation.
---

# Flux GitOps Workflow

## Repository layout (mono-repo)

Kubernetes GitOps uses **one folder per cluster** under `clusters/`. Production and test share this repo but **never** share the same Flux `path:` on the cluster.

| Path | Purpose |
|------|---------|
| `clusters/test-deployment/` | Test cluster |
| `clusters/production/` | Production k0s cluster |

See [`clusters/README.md`](../../../clusters/README.md) for when to split into a second repository (compliance, org boundaries).

Shared Kustomize primitives can live under [`bases/`](../../../bases/README.md) and be referenced with relative paths from each cluster.

## Namespace naming

Use explicit names **`appname-environment`** (all lowercase, words separated by **hyphens**), where:

- **`appname`** is a short slug for the workload or shared stack (e.g. `clutterstock-api`, `homepage`, `observability`).
- **`environment`** is the deployment line (e.g. `test`, `qa`, `staging`, `production`, or `preview` for ephemeral PR deploys).

**Always include `environment`**, even when an app only runs in production (e.g. `clutterstock-frontend-production`), so names stay consistent and PR/preview namespaces stay obvious.

Guidelines:

- **DNS label rules** (for namespaces and for hostname slugs): only `[a-z0-9-]`, start/end with alphanumeric, max **63 characters** per label. Shorten long `appname` slugs if the composite hostname would exceed limits.
- **Ephemeral / PR** namespaces stay **`appname-preview`** (or `appname-preview-pr-<n>` if you need one namespace per PR). **Public hostnames** for previews use [`{appname}-{pr-number}.preview.wsh.no`](#public-hostnames-wshno) so a single TLS wildcard `*.preview.wsh.no` is enough.
- **Shared platform** (ingress controller namespace, observability stack, etc.) use **`platform-<environment>`** when there is no single product `appname`.
- Git folder names and Flux paths do not have to mirror namespace strings, but aligning them reduces mistakes.

## Public hostnames (`wsh.no`)

**Ingress `spec.rules.host`** (and public DNS) use the domain **`wsh.no`**, separate from in-cluster DNS (`*.svc.cluster.local`). Namespaces do not allocate IPs or public names; map workloads with Ingress (e.g. Traefik) + DNS records.

| Environment | Host pattern | Example |
|-------------|----------------|---------|
| **Production (apps)** | `{service}.wsh.no` | `clutterstock.wsh.no`, `api-clutterstock.wsh.no` |
| **Production (management)** | Homepage: `mgmt.wsh.no`; other services: `{service}.mgmt.wsh.no` | `mgmt.wsh.no`, `grafana.mgmt.wsh.no` |
| **Test** | `appname.test.wsh.no` or cluster-specific zones (e.g. `*.kt.wsh.no`) | `clutterstock.test.wsh.no`, `grafana.mgmt-kt.wsh.no` |
| **PR / preview** | `appname-<pr-number>.preview.wsh.no` | `clutterstock-184.preview.wsh.no` |

**PR/preview shape:** put **`appname`** and **`pr-number`** in one DNS label left of `preview.wsh.no` (`clutterstock-184`), not `184.clutterstock.preview.wsh.no`, so **`*.preview.wsh.no`** covers all preview hosts without per-app wildcards.

Use lowercase slugs; **do not** put raw Git branch names in host labels (sanitize to `[a-z0-9-]`). Keep the first label ≤63 characters.

## Cluster layout (per environment)

Each directory matches the same high-level shape:

```
clusters/<name>/
├── kustomization.yaml          # Root: includes flux-system + apps
├── README.md                    # Bootstrap notes (production has GitHub bootstrap command)
├── flux-system/
│   ├── gotk-components.yaml    # Auto-generated Flux controllers (DO NOT EDIT)
│   ├── gotk-sync.yaml          # GitRepository + root Flux Kustomization for THIS path only
│   └── kustomization.yaml
└── apps/
    ├── kustomization.yaml
    └── ...
```

**Test cluster** (`clusters/test-deployment/apps/`) includes raw deployments, `ingress.yaml`, `traefik-helmrelease.yaml`, `observability/`, `kubevious/`, `homepage/`, `clutterstock-migrate/`, etc.

**Production** (`clusters/production/`) starts minimal; add workloads under `apps/` as you promote them from test patterns.

## Sync configuration

### Test (`clusters/test-deployment/flux-system/gotk-sync.yaml`)

- **GitRepository** `flux-system` watches `https://github.com/hwinther/proxmox.git`, branch `main`, interval 1m.
- **Flux Kustomization** `clutterstock-migrate` syncs `./clusters/test-deployment/apps/clutterstock-migrate` with prune enabled.
- **Flux Kustomization** `flux-system` syncs `./clusters/test-deployment` with prune enabled and `dependsOn: clutterstock-migrate`.

The dependency ensures migration jobs run before the main app bundle reconciles.

### Production (`clusters/production/flux-system/gotk-sync.yaml`)

- Same **GitRepository** pattern (URL/branch/`secretRef` as appropriate for the prod cluster).
- **Kustomization** `clutterstock-migrate` with `path: ./clusters/production/apps/clutterstock-migrate` (namespace + PVC + migrator Job).
- Root **Kustomization** `flux-system` with `path: ./clusters/production` and **`dependsOn: clutterstock-migrate`** so Clutterstock storage exists before the main app bundle.

Bootstrap production with `flux bootstrap github --path=clusters/production` (see `clusters/production/README.md`). Each cluster gets its own in-cluster `flux-system` secret for Git; do not copy test cluster kubeconfig secrets to prod.

## Adding a new app (single manifest)

Ensure the app uses a Namespace matching **`appname-environment`** (see [Namespace naming](#namespace-naming)); reference it in manifests via `metadata.namespace` or a Namespace resource in the same kustomization.

For **test**, use `clusters/test-deployment/apps/`:

1. Create `clusters/test-deployment/apps/<app>-deployment.yaml` with Deployment + Service.
2. Add the filename to the `resources` list in `clusters/test-deployment/apps/kustomization.yaml`.
3. If the app needs an Ingress, append a new `---` document to `clusters/test-deployment/apps/ingress.yaml` using the [public hostname](#public-hostnames-wshno) for the environment (`appname.test.wsh.no` on the test cluster, etc.).
4. Commit to `main`. Flux picks up the change within 1 minute.

For **production**, mirror the same pattern under `clusters/production/apps/` and list resources in `clusters/production/apps/kustomization.yaml`.

## Adding a new sub-kustomization

For apps with multiple manifests (HelmRelease, namespace, configmaps):

1. Create a subdirectory under the target cluster’s `apps/`, e.g. `clusters/test-deployment/apps/my-stack/` or `clusters/production/apps/my-stack/`.
2. Add a `kustomization.yaml` inside it listing its resources.
3. Add the directory name to that cluster’s `apps/kustomization.yaml`:

```yaml
resources:
  - existing-file.yaml
  - my-stack          # directory name, not the kustomization.yaml path
```

4. Commit to `main`.

## Updating an Image Tag

Deployments pin semver tags (never `latest`). To roll out a new version:

1. Update the `image:` field in the relevant `*-deployment.yaml`, e.g.:

```yaml
image: ghcr.io/hwinther/test/api:0.54.0   # was 0.53.1
```

2. Commit to `main`. Flux reconciles and Kubernetes performs a rolling update.

## Adding a Flux dependency

To make one Kustomization wait for another, edit that cluster’s `flux-system/gotk-sync.yaml` and add a `dependsOn` entry. Only add dependencies when ordering truly matters (e.g., migrations before app startup). Prefer keeping prod `gotk-sync` minimal.

## Key rules

- New namespaced resources use **`appname-environment`** namespaces (see [Namespace naming](#namespace-naming)).
- Ingress and DNS follow **`wsh.no`** patterns in [Public hostnames](#public-hostnames-wshno) (`appname.wsh.no`, `appname.test.wsh.no`, `appname-<pr>.preview.wsh.no`).
- **Never edit** `gotk-components.yaml` -- it is regenerated by `flux bootstrap` / `flux install --export`.
- All changes deploy via **git**; avoid ad-hoc `kubectl apply` for GitOps-managed resources.
- Flux prune is enabled: removing a resource from the kustomization deletes it from the cluster.
- Use `kubectl get kustomization -n flux-system` and `flux get all` to check reconciliation status.
- Keep **production** sync scoped to `./clusters/production`; never point a prod cluster at `./clusters/test-deployment`.
