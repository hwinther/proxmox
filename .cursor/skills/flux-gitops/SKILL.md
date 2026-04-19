---
name: flux-gitops
description: >-
  Manage the Flux GitOps workflow for the Kubernetes cluster in this repo.
  Use when adding, removing, or updating apps synced by Flux, working with
  Kustomization resources, troubleshooting Flux reconciliation, or placing
  workloads relative to shared platform pieces (Postgres tiers, Valkey, etc.).
---

# Flux GitOps Workflow

## Repository layout (mono-repo)

Kubernetes GitOps uses **one folder per cluster** under `clusters/`. Production and test share this repo but **never** share the same Flux `path:` on the cluster.

| Path                        | Purpose                |
| --------------------------- | ---------------------- |
| `clusters/test-deployment/` | Test cluster           |
| `clusters/production/`      | Production k0s cluster |

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

| Environment                         | Host pattern                                                         | Example                                                                                                                                                                                                                                                                                     |
| ----------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Production (apps)**               | `{service}.wsh.no`                                                   | `clutterstock.wsh.no` (API at `/api/`)                                                                                                                                                                                                                                                      |
| **Production (management)**         | Homepage: `mgmt.wsh.no`; other services: `{service}.mgmt.wsh.no`     | `mgmt.wsh.no`, `grafana.mgmt.wsh.no`, `headlamp.mgmt.wsh.no`                                                                                                                                                                                                                                |
| **Production (SSO / OIDC issuer)**  | **Canonical:** `auth.wsh.no` only                                    | `https://auth.wsh.no` — Authelia (`iss`, session URL) + apiserver `oidc-issuer-url`; see [`authelia-helmrelease.yaml`](../../../clusters/production/apps/authelia-production/authelia-helmrelease.yaml). Keep **`*.mgmt.wsh.no`** private; public apps redirect login to **`auth.wsh.no`**. |
| **Test**                            | `appname.test.wsh.no` or cluster-specific zones (e.g. `*.kt.wsh.no`) | `clutterstock.test.wsh.no`, `grafana.mgmt-kt.wsh.no`                                                                                                                                                                                                                                        |
| **Test-tier DNS (on prod cluster)** | `*.test.wsh.no`                                                      | `test.test.wsh.no` — namespace **`test-test`** (app **test** + env **test**); ([`clusters/production/apps/test-test/`](../../../clusters/production/apps/test-test/README.md))                                                                                                              |
| **PR / preview**                    | `appname-<pr-number>.preview.wsh.no`                                 | `clutterstock-184.preview.wsh.no`                                                                                                                                                                                                                                                           |

**PR/preview shape:** put **`appname`** and **`pr-number`** in one DNS label left of `preview.wsh.no` (`clutterstock-184`), not `184.clutterstock.preview.wsh.no`, so **`*.preview.wsh.no`** covers all preview hosts without per-app wildcards.

**Kubernetes API + Authelia OIDC (production):** After adding **`oidc-*`** `extraArgs` on controllers (see commented template in [`infra/k0s/k0s.yaml.example`](../../../infra/k0s/k0s.yaml.example)), grant access with **`ClusterRoleBinding`** subjects that match JWT claims. Production GitOps includes [`clusters/production/apps/oidc-k8s-admins-rbac/`](../../../clusters/production/apps/oidc-k8s-admins-rbac/) (**`Group` `k8s-admins`** → **`cluster-admin`**). Adjust or replace that binding if you use a different LDAP group name or want a narrower `ClusterRole`. Usernames typically align with LDAP **`uid`** (`oidc-username-claim: preferred_username`).

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

**Production** (`clusters/production/apps/`) lists **`shared/production`** and **`shared/test`** before app bundles so **`shared-production`** / **`shared-test`** (Redis, etc.) exist first — see [`clusters/production/apps/shared/README.md`](../../../clusters/production/apps/shared/README.md).

## PostgreSQL (CloudNative-PG)

**Preferred relational database** on Kubernetes in this repo is **[CloudNative-PG](https://cloudnative-pg.io/)** (CNPG): GitOps-managed `Cluster` resources under shared namespaces, with the operator installed from **`clusters/production/apps/cnpg-system/`** (HelmRelease in **`cnpg-system`**). Avoid ad-hoc single-replica Postgres Deployments unless there is a strong reason.

### Tiering on the production k0s cluster (`clusters/production/`)

| Namespace / bundle | Tier | Purpose |
| ------------------ | ---- | ------- |
| **`postgres-test`** | **Test** | CNPG `Cluster`s for workloads on the **test line** (namespaces like **`test-test`**, **`clutterstock-test`**): e.g. `testdb`, `cluttertestdb`. |
| **`postgres-production`** | **Production** | CNPG `Cluster`s for **production-line** apps (e.g. **`clutterstock-production`**): e.g. `clutterstockdb`. |

**Rule:** test-tier apps use Postgres **only** from **`postgres-test`**; production-tier apps use Postgres **only** from **`postgres-production`**. Do not cross-wire tiers (same cluster, different namespaces and PVCs).

### Connection strings and Secrets

- CNPG creates **`<cluster>-app`** Secrets in the **same namespace** as the `Cluster` (e.g. `testdb-app` in `postgres-test`).
- Pods in **app** namespaces cannot `secretKeyRef` across namespaces; this repo uses **Kyverno** `ClusterPolicy` rules to **clone** the `-app` Secret into the consumer namespace (`test-test`, `clutterstock-test`, `clutterstock-production`, …).
- Document operator-created credentials and clone behavior in **[`postgres-test-secrets.md`](../../../clusters/production/apps/postgres-test/postgres-test-secrets.md)** and **[`postgres-production-secrets.md`](../../../clusters/production/apps/postgres-production/postgres-production-secrets.md)** (not committed `Secret` manifests).
- **NetworkPolicy:** allow app namespace → **`postgres-test:5432`** or **`postgres-production:5432`** as appropriate; CNPG pods allow ingress from listed client namespaces and from **Adminer** where deployed.

### Adminer (SQL UI)

- **Test tier:** Ingress **`adminer-pg-test.mgmt.wsh.no`** (namespace **`postgres-test`**, Authelia).
- **Production tier:** **`adminer-pg-prod.mgmt.wsh.no`** (namespace **`postgres-production`**).
- Both register on **Homepage** via **`gethomepage.dev/*`** Ingress annotations while [`homepage.yaml`](../../../clusters/production/apps/homepage/homepage.yaml) keeps **`kubernetes.yaml`** `ingress: true`.

### Separate test Kubernetes cluster (`clusters/test-deployment/`)

That Flux root targets a **different** cluster: CNPG operator under **`cnpg-system/`** and a **`Cluster`** (e.g. **`testdb`** in namespace **`test`**, `local-path` storage) under **`cnpg-test/`**. It is **not** the same Postgres instance as production k0s `postgres-test` / `postgres-production`.

### PR / ephemeral previews

For **`appname-preview`** namespaces, either provision a **dedicated small `Cluster`** per preview (RAM cost scales with cluster count), reuse a shared preview Postgres with **strict DB/user naming**, or defer Postgres until requirements are clear — see [Namespace naming](#namespace-naming) for hostname patterns.

## Sync configuration

### Test (`clusters/test-deployment/flux-system/gotk-sync.yaml`)

- **GitRepository** `flux-system` watches `https://github.com/hwinther/proxmox.git`, branch `main`, interval 1m.
- **Flux Kustomization** `clutterstock-migrate` syncs `./clusters/test-deployment/apps/clutterstock-migrate` with prune enabled.
- **Flux Kustomization** `flux-system` syncs `./clusters/test-deployment` with prune enabled and `dependsOn: clutterstock-migrate`.

The dependency ensures migration jobs run before the main app bundle reconciles.

### Production (`clusters/production/flux-system/gotk-sync.yaml`)

- Same **GitRepository** pattern (URL/branch/`secretRef` as appropriate for the prod cluster).
- **Kustomization** `clutterstock-migrate` with `path: ./clusters/production/apps/clutterstock-migrate` (namespace + PVC + migrator Job).
- Root **Kustomization** `flux-system` with `path: ./clusters/production` — **no `dependsOn` migrate**, so a stuck Clutterstock PVC/Job does not block observability, Traefik, or Homepage. Ensure migrator Job has completed before depending on Clutterstock API.

Bootstrap production with `flux bootstrap github --path=clusters/production` (see `clusters/production/README.md`). Each cluster gets its own in-cluster `flux-system` secret for Git; do not copy test cluster kubeconfig secrets to prod.

## Adding a new app (single manifest)

Ensure the app uses a Namespace matching **`appname-environment`** (see [Namespace naming](#namespace-naming)); reference it in manifests via `metadata.namespace` or a Namespace resource in the same kustomization.

For **test**, use `clusters/test-deployment/apps/`:

1. Create `clusters/test-deployment/apps/<app>-deployment.yaml` with Deployment + Service.
2. Add the filename to the `resources` list in `clusters/test-deployment/apps/kustomization.yaml`.
3. If the app needs an Ingress, append a new `---` document to `clusters/test-deployment/apps/ingress.yaml` using the [public hostname](#public-hostnames-wshno) for the environment (`appname.test.wsh.no` on the test cluster, etc.).
4. Commit to `main`. Flux picks up the change within 1 minute.

For **production**, mirror the same pattern under `clusters/production/apps/` and list resources in `clusters/production/apps/kustomization.yaml`.

Before opening the PR, reconcile **Kyverno / Cilium / image policy** in the same change when needed: see [**.cursor/skills/k8s-kyverno-kubescape-compliance/SKILL.md**](../k8s-kyverno-kubescape-compliance/SKILL.md) (**“Before the first commit”**, **PolicyExceptions**, Traefik host ingress) so Flux does not apply a broken Deployment first and require follow-up commits for exceptions or `CiliumNetworkPolicy` fixes.

## Adding a new sub-kustomization

For apps with multiple manifests (HelmRelease, namespace, configmaps):

1. Create a subdirectory under the target cluster’s `apps/`, e.g. `clusters/test-deployment/apps/my-stack/` or `clusters/production/apps/my-stack/`.
2. Add a `kustomization.yaml` inside it listing its resources.
3. Add the directory name to that cluster’s `apps/kustomization.yaml`:

```yaml
resources:
  - existing-file.yaml
  - my-stack # directory name, not the kustomization.yaml path
```

4. Commit to `main`.

## Updating an Image Tag

Deployments pin semver tags (never `latest`). To roll out a new version:

1. Update the `image:` field in the relevant `*-deployment.yaml`, e.g.:

```yaml
image: ghcr.io/hwinther/test/api:0.54.0 # was 0.53.1
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
