# Cluster GitOps paths

## Repository strategy (mono-repo)

Production and edge Kubernetes GitOps live in **this repository** under separate directories:

- `clusters/production/` — production k0s cluster (Flux sync path: `./clusters/production`)
- `clusters/edge-sdr/` — edge k0s cluster for SDR-only workloads on the radio-pi nodes (Flux sync path: `./clusters/edge-sdr`)

**Rationale:** One Git repository keeps a single Flux `GitRepository` URL, shared conventions, and optional shared Kustomize bases under [`bases/`](../bases/README.md). Each cluster is isolated by **sync path** and **in-cluster** credentials, not by a second repo.

**Use a separate Git repository** if you require a different org or access model, regulatory separation, or CI/credential isolation such that experimental changes must never share tooling with production.

Each cluster has its **own** Flux bootstrap and `flux-system/gotk-sync.yaml`; do not cross-point sync manifests between them.

## Namespace naming

Use **`appname-environment`** (lowercase, hyphenated): always include the environment segment, even for production-only apps (e.g. `myapp-production`). Shared cluster stacks (ingress, observability) may use **`platform-<environment>`**. See [.cursor/skills/flux-gitops/SKILL.md](../.cursor/skills/flux-gitops/SKILL.md) for PR preview examples and length rules.

## Public hostnames (`wsh.no`)

| Environment  | Pattern                              | Example                           |
| ------------ | ------------------------------------ | --------------------------------- |
| Production   | `appname.wsh.no`                     | `clutterstock.wsh.no`             |
| Test tier (on production cluster) | `appname.test.wsh.no`                | `clutterstock.test.wsh.no`        |
| PR / preview | `appname-<pr-number>.preview.wsh.no` | `clutterstock-184.preview.wsh.no` |

Preview hosts use **`{appname}-{pr}`** as a single label before `preview.wsh.no` so one wildcard **`*.preview.wsh.no`** suffices. Details: [.cursor/skills/flux-gitops/SKILL.md](../.cursor/skills/flux-gitops/SKILL.md).

## Links

- Platform bootstrap order (Proxmox, Ceph, Cilium, k0s, CSI, Flux): [`../infra/k0s/README.md`](../infra/k0s/README.md)
- Day-to-day Flux workflow: [`.cursor/skills/flux-gitops/SKILL.md`](../.cursor/skills/flux-gitops/SKILL.md)
