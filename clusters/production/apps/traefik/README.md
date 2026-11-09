# Traefik (production)

- **hostNetwork** — Backends reached via Ingress are dialed from the **node** network identity (Cilium `host` / `remote-node`), not the `traefik` pod namespace. Tight `NetworkPolicy` rules that only allow `namespaceSelector: traefik` are not enough; workloads behind those policies need a **`CiliumNetworkPolicy`** allowing `fromEntities: [host, remote-node]` on the Service port (see e.g. `clutterstock/cilium-cluster-nodes-to-http.yaml`, `observability/cilium-host-to-otel-otlp-http.yaml` for OTLP HTTP **4318**). Without that, the edge proxy can see **504 / gateway timeout** or **browser CORS errors** (failed preflight shows as missing `Access-Control-Allow-Origin` because Traefik never completes the middleware chain) while `kubectl port-forward` to the same Service still works.
- **`traefik-crds.yaml`** — CRDs from `helm show crds traefik/traefik --version 39.0.7`. Committed so Flux can apply `Middleware` / `IngressRoute` objects (e.g. in `observability`) in the same reconcile as this chart; without CRDs in Git, `kubectl`/Flux dry-run fails with _no matches for kind "Middleware"_ before Helm installs the chart.
- **`traefik-helmrelease.yaml`** — HelmRelease pins chart **`39.0.7`** and uses **`install.crds: Skip`** / **`upgrade.crds: Skip`** so CRD lifecycle is owned by `traefik-crds.yaml`, not Helm.

## Gateway API (migration from Ingress)

- The `kubernetesGateway` provider is enabled next to the Ingress provider. The CRDs (standard channel, the version Traefik documents) are in `../gateway-api`.
- `gateway.yaml` is the single platform Gateway `traefik/traefik`. Its listener `web` is on port 8000, which must match the `web` entryPoint.
- App namespaces opt in with the label `gateway.wsh.no/traefik: "true"`. Routes use `parentRefs: [{name: traefik, namespace: traefik, sectionName: web}]`.
- **ForwardAuth:** an HTTPRoute references a Middleware with an `ExtensionRef` filter (`group: traefik.io`, `kind: Middleware`). The reference is namespace-local, so the shared `authelia-production/authelia-forwardauth` that the Ingresses use can't be referenced across namespaces. Kyverno therefore generates a copy named `authelia-forwardauth` in every namespace with the opt-in label (`../platform-production/kyverno-generatingpolicy-generate-forwardauth-middleware.yaml`). The source stays in authelia-production.
- **Hostnames:** `httproute-hostnames-policy.yaml` (ValidatingAdmissionPolicy) only admits an HTTPRoute whose `spec.hostnames` are all listed in the namespace annotation `gateway.wsh.no/hostnames` (comma-separated, exact). Routes without hostnames are rejected too. To onboard an app, add the label and this annotation to its `namespace.yaml`.
- Pilot: `../test-test/gateway-pilot.yaml`.

After upgrading the Traefik chart version, re-export CRDs and replace `traefik-crds.yaml`:

```bash
helm repo update traefik
helm show crds traefik/traefik --version <new-version> > clusters/production/apps/traefik/traefik-crds.yaml
```
