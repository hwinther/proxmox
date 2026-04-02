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

[`flux-system/gotk-sync.yaml`](flux-system/gotk-sync.yaml) defines a `GitRepository` and a single root `Kustomization` with `path: ./clusters/production` and **no** dependency on test-only paths (for example migration jobs that exist only under `test-deployment`).

Platform checklist before apps: [`../../infra/k0s/README.md`](../../infra/k0s/README.md). **Ceph RBD:** Flux manifests under [`apps/ceph-csi/`](apps/ceph-csi/README.md) (fill in FSID/monitors, create `csi-rbd-secret` before expecting PVCs).

## Namespace naming

Follow **`appname-environment`** (lowercase, hyphens): include the environment in every app namespace, including production-only workloads (e.g. `clutterstock-api-production`). Use **`platform-production`** (or `platform-<env>`) for shared platform namespaces. Details: [`.cursor/skills/flux-gitops/SKILL.md`](../../.cursor/skills/flux-gitops/SKILL.md).

The placeholder namespace under `apps/` is `platform-production` for cluster-wide GitOps-owned resources until real apps add their own `*-namespace.yaml` files.

## Public hostnames (`wsh.no`)

Production Ingress hosts use **`appname.wsh.no`** (e.g. `clutterstock.wsh.no`). Non-prod uses **`appname.test.wsh.no`**; PR previews use **`appname-<pr-number>.preview.wsh.no`** (e.g. `clutterstock-184.preview.wsh.no`). See [`.cursor/skills/flux-gitops/SKILL.md`](../../.cursor/skills/flux-gitops/SKILL.md).
