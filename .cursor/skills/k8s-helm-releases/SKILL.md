---
name: k8s-helm-releases
description: >-
  Add and configure Flux HelmRepository and HelmRelease resources in this repo.
  Use when installing a new Helm chart, updating chart versions, configuring
  Helm values, or troubleshooting HelmRelease reconciliation.
---

# HelmRelease Resources

## Overview

This repo uses Flux HelmRelease CRDs (not `helm install`) to deploy Helm charts. Charts are pulled from HelmRepository sources and reconciled by Flux.

## File Locations

- **Traefik:** `clusters/test-deployment/apps/traefik-helmrelease.yaml` (includes Namespace + HelmRepository + HelmRelease in one file)
- **Observability stack:** `clusters/test-deployment/apps/observability/` with separate files for each release
- **Kubevious:** `clusters/test-deployment/apps/kubevious/`

HelmRepositories for the observability stack are consolidated in `clusters/test-deployment/apps/observability/helmrepositories.yaml`.

## HelmRepository Template

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: <repo-name>
  namespace: <namespace>
spec:
  interval: 1h
  url: https://example.github.io/helm-charts
```

- API version: `source.toolkit.fluxcd.io/v1`
- Interval: `1h` (how often Flux checks for new chart versions)
- Place in the same namespace as the HelmRelease that references it

## HelmRelease Template

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: <release-name>
  namespace: <namespace>
spec:
  interval: 30m
  chart:
    spec:
      chart: <chart-name>
      version: "<version-constraint>"
      sourceRef:
        kind: HelmRepository
        name: <repo-name>
        namespace: <namespace>
  values:
    # Chart-specific values here
```

- API version: `helm.toolkit.fluxcd.io/v2`
- Interval: `30m` (reconciliation frequency)
- Add `timeout: 10m` for charts with slow startup (e.g. Grafana waiting on dependencies)

## Version Pinning

Two strategies used in this repo:

| Strategy | Example | When to use |
|---|---|---|
| Semver range | `'>=26.0.0'` | Stable charts where auto-upgrading is acceptable (e.g. Traefik) |
| Exact version | `"10.5.15"` | Charts where values schema may break across versions (e.g. Grafana) |

Quote version strings in YAML to prevent type coercion.

## Dependency Ordering

Use `dependsOn` when a release needs another to be ready first:

```yaml
spec:
  dependsOn:
    - name: obs-prometheus
      namespace: test
    - name: obs-loki
      namespace: test
```

In this repo, Grafana depends on Prometheus, Loki, and Tempo. Expect 404s on Grafana's ingress until all dependencies are Ready.

## Naming Conventions

- Observability releases: prefix with `obs-` (e.g. `obs-prometheus`, `obs-grafana`, `obs-otel-collector`)
- Other releases: use the chart name directly (e.g. `traefik`, `kubevious`)

## Namespace Placement

| Stack | Namespace |
|---|---|
| App workloads + observability | `test` |
| Traefik ingress controller | `traefik` (own namespace, created in the same file) |
| Kubevious | `kubevious` |

When a chart needs its own namespace, include a `kind: Namespace` document above the HelmRelease in the same file or kustomization.

## Storage Considerations

This cluster may lack a default StorageClass. For charts that default to PVC-backed persistence:

- Set `persistence.enabled: false` in values
- Use `extraVolumes` / `extraVolumeMounts` with `emptyDir` where the chart still needs a writable path (e.g. Loki's `/var/loki`)
- Disable components that require hostPort if Traefik already uses hostNetwork (e.g. `prometheus-node-exporter`)

For production, add a StorageClass (e.g. `local-path-provisioner`) and re-enable persistence.

## Adding a New HelmRelease

1. Add a `HelmRepository` for the chart source (or reuse an existing one from `helmrepositories.yaml`).
2. Create a `<name>-helmrelease.yaml` with the HelmRelease spec.
3. Add both files to the relevant `kustomization.yaml` under `resources`.
4. If the chart needs a dedicated namespace, add a `Namespace` resource.
5. If the chart needs an Ingress, add it to `ingress.yaml` or a dedicated ingress file in the sub-kustomization.
6. Commit to `main`.

## Troubleshooting

```bash
# Check HelmRelease status
kubectl get helmrelease -n <namespace>
flux get helmrelease -n <namespace>

# See why a release failed
kubectl describe helmrelease <name> -n <namespace>

# Force reconciliation
flux reconcile helmrelease <name> -n <namespace>

# If stale values persist after chart changes, uninstall and let Flux reinstall
helm uninstall <name> -n <namespace>
```
