---
name: k8s-traefik-ingress
description: >-
  Configure Traefik Ingress resources with Homepage dashboard integration.
  Use when adding or modifying Ingress rules, setting up DNS hostnames,
  configuring Homepage annotations, or troubleshooting routing issues.
---

# Traefik Ingress Configuration

## Ingress File

All app Ingress resources live in a single file: `clusters/test-deployment/apps/ingress.yaml`, separated by `---`. Observability Ingress entries have their own file at `clusters/test-deployment/apps/observability/observability-ingress.yaml`.

## Traefik Setup

Traefik is deployed as a DaemonSet with `hostNetwork: true` via HelmRelease in `clusters/test-deployment/apps/traefik-helmrelease.yaml`. It listens on:

| Entrypoint | Port | Purpose |
|---|---|---|
| `web` | 8000 | HTTP traffic |
| `websecure` | 8444 | HTTPS traffic |
| `traefik` | 9000 | Dashboard (not exposed) |

## DNS Zones

| Zone | Purpose | Examples |
|---|---|---|
| `*.kt.wsh.no` | Public-facing apps | `test.kt.wsh.no`, `api.kt.wsh.no`, `clutterstock.kt.wsh.no` |
| `*.mgmt-kt.wsh.no` | Management/ops UIs | `mgmt-kt.wsh.no`, `redis.mgmt-kt.wsh.no`, `grafana.mgmt-kt.wsh.no` |

Management zone should have stricter access controls (IP allowlists, Authelia, etc.) at the external reverse proxy.

## Ingress Template

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: <app-name>
  namespace: test
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
    gethomepage.dev/enabled: "true"
    gethomepage.dev/group: <Applications|Management>
    gethomepage.dev/name: <Display Name>
    gethomepage.dev/icon: <icon-name>
    gethomepage.dev/description: <Short description>
spec:
  rules:
  - host: <hostname>
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: <service-name>
            port:
              number: 8080
```

## Required Annotations

### Traefik

- `traefik.ingress.kubernetes.io/router.entrypoints: web` -- routes through the HTTP entrypoint. Use `websecure` for TLS-terminated routes.

### Homepage Dashboard

These annotations register the service in the Homepage dashboard automatically:

| Annotation | Value | Notes |
|---|---|---|
| `gethomepage.dev/enabled` | `"true"` | Must be string `"true"` |
| `gethomepage.dev/group` | `Applications` or `Management` | Groups in the dashboard |
| `gethomepage.dev/name` | Display name | Human-readable name |
| `gethomepage.dev/icon` | Icon identifier | MDI icons (`mdi-*`) or named icons (`redis`, `homepage`) |
| `gethomepage.dev/description` | Short text | Shown below the name |

## Backend Port

- Use `port.number: 8080` for standard app services (matches the `http` named port in Service specs).
- Use the actual port number for non-standard services (e.g. `5540` for RedisInsight, `3000` for Homepage).

## Adding a New Ingress Entry

1. Choose the hostname based on the DNS zone convention:
   - App: `<name>.kt.wsh.no`
   - Management UI: `<name>.mgmt-kt.wsh.no`
2. Append a new `---` separated Ingress document to `clusters/test-deployment/apps/ingress.yaml`.
3. Include both Traefik and Homepage annotations.
4. Ensure the referenced Service exists (from a `*-deployment.yaml` or HelmRelease).
5. Commit to `main`.

## Troubleshooting

- **404 on a hostname:** Verify DNS resolves to a Traefik node, the `Host` header matches the Ingress rule, and the backend Service + Endpoints exist (`kubectl get endpoints -n test <service>`).
- **CORS issues (browser OTLP):** Add Traefik CORS middleware if the web app origin differs from the OTLP ingress host. Include `traceparent`, `tracestate`, and `baggage` in `accessControlAllowHeaders` when browsers send them. Same-host path routing (e.g. UI + `/api` on one hostname) avoids CORS for those API requests; Traefik forwards inbound client headers to backends by default.
- **Blank page from chart-managed Ingress (e.g. Kubevious):** Check all pods are Running and the Service has Endpoints.
