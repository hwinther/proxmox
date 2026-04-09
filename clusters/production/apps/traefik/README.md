# Traefik (production)

- **hostNetwork** — Backends reached via Ingress are dialed from the **node** network identity (Cilium `host` / `remote-node`), not the `traefik` pod namespace. Tight `NetworkPolicy` rules that only allow `namespaceSelector: traefik` are not enough; workloads behind those policies need a **`CiliumNetworkPolicy`** allowing `fromEntities: [host, remote-node]` on the Service port (see e.g. `clutterstock/cilium-cluster-nodes-to-http.yaml`, `observability/cilium-host-to-otel-otlp-http.yaml` for OTLP HTTP **4318**). Without that, the edge proxy can see **504 / gateway timeout** or **browser CORS errors** (failed preflight shows as missing `Access-Control-Allow-Origin` because Traefik never completes the middleware chain) while `kubectl port-forward` to the same Service still works.
- **`traefik-crds.yaml`** — CRDs from `helm show crds traefik/traefik --version 39.0.7`. Committed so Flux can apply `Middleware` / `IngressRoute` objects (e.g. in `observability`) in the same reconcile as this chart; without CRDs in Git, `kubectl`/Flux dry-run fails with *no matches for kind "Middleware"* before Helm installs the chart.
- **`traefik-helmrelease.yaml`** — HelmRelease pins chart **`39.0.7`** and uses **`install.crds: Skip`** / **`upgrade.crds: Skip`** so CRD lifecycle is owned by `traefik-crds.yaml`, not Helm.

After upgrading the Traefik chart version, re-export CRDs and replace `traefik-crds.yaml`:

```bash
helm repo update traefik
helm show crds traefik/traefik --version <new-version> > clusters/production/apps/traefik/traefik-crds.yaml
```
