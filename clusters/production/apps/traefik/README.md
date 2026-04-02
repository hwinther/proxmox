# Traefik (production)

- **`traefik-crds.yaml`** — CRDs from `helm show crds traefik/traefik --version 39.0.7`. Committed so Flux can apply `Middleware` / `IngressRoute` objects (e.g. in `observability`) in the same reconcile as this chart; without CRDs in Git, `kubectl`/Flux dry-run fails with *no matches for kind "Middleware"* before Helm installs the chart.
- **`traefik-helmrelease.yaml`** — HelmRelease pins chart **`39.0.7`** and uses **`install.crds: Skip`** / **`upgrade.crds: Skip`** so CRD lifecycle is owned by `traefik-crds.yaml`, not Helm.

After upgrading the Traefik chart version, re-export CRDs and replace `traefik-crds.yaml`:

```bash
helm repo update traefik
helm show crds traefik/traefik --version <new-version> > clusters/production/apps/traefik/traefik-crds.yaml
```
