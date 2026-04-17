---
name: k8s-traefik-ingress
description: >-
  Configure Traefik Ingress resources with Homepage dashboard integration.
  Use when adding or modifying Ingress rules, setting up DNS hostnames,
  configuring Homepage annotations, Authelia forward-auth on production,
  or troubleshooting routing issues.
---

# Traefik Ingress Configuration

## Ingress File

**Test cluster:** app Ingress documents live in `clusters/test-deployment/apps/ingress.yaml`, separated by `---`. Observability Ingress entries have their own file at `clusters/test-deployment/apps/observability/observability-ingress.yaml`.

**Production:** many apps use the same multi-document style in [`clusters/production/apps/ingress.yaml`](../../../clusters/production/apps/ingress.yaml); some stacks keep a dedicated `*-ingress.yaml` next to the app (e.g. observability, Headlamp). Follow the existing pattern for the workload you touch.

## Traefik Setup

Traefik is deployed as a DaemonSet with `hostNetwork: true` via HelmRelease in `clusters/test-deployment/apps/traefik-helmrelease.yaml`. It listens on:

| Entrypoint  | Port | Purpose                 |
| ----------- | ---- | ----------------------- |
| `web`       | 8000 | HTTP traffic            |
| `websecure` | 8444 | HTTPS traffic           |
| `traefik`   | 9000 | Dashboard (not exposed) |

## DNS Zones

| Zone               | Purpose            | Examples                                                           |
| ------------------ | ------------------ | ------------------------------------------------------------------ |
| `*.kt.wsh.no`      | Public-facing apps | `test.kt.wsh.no`, `api.kt.wsh.no`, `clutterstock.kt.wsh.no`        |
| `*.mgmt-kt.wsh.no` | Management/ops UIs | `mgmt-kt.wsh.no`, `redis.mgmt-kt.wsh.no`, `grafana.mgmt-kt.wsh.no` |

Management zone should have stricter access controls (IP allowlists, Authelia, etc.) at the external reverse proxy.

## Production: Authelia + hostnames (`wsh.no`)

- **OIDC issuer + Authelia portal:** **`auth.wsh.no`** — canonical **`https://auth.wsh.no`** for JWT `iss`, Authelia session `authelia_url`, Headlamp **`issuerURL`**, and kube-apiserver **`oidc-issuer-url`**. Implemented under [`clusters/production/apps/authelia-production/authelia-helmrelease.yaml`](../../../clusters/production/apps/authelia-production/authelia-helmrelease.yaml) (Traefik entrypoint **`web`** on that host).
- **Management UIs:** **`{service}.mgmt.wsh.no`** (and Homepage **`mgmt.wsh.no`**) — keep these on the management network / stricter edge; they are **not** the OIDC issuer hostname.
- **Traefik ForwardAuth** behind Authelia for a UI: see [`clusters/production/apps/headlamp-production/traefik-middleware-authelia-forwardauth.yaml`](../../../clusters/production/apps/headlamp-production/traefik-middleware-authelia-forwardauth.yaml) — reference the Middleware on the Ingress with `traefik.ingress.kubernetes.io/router.middlewares: <ns>-authelia-forwardauth@kubernetescrd`. Add matching **`access_control`** rules in the Authelia HelmRelease for that **`Host`** / paths (bypass only narrow paths such as health checks or OIDC callbacks when documented there).
- **New OIDC clients:** extend `identity_providers.oidc.clients` on the Authelia HelmRelease; include every **`redirect_uris`** HTTPS origin the app uses.
- **API access for humans:** LDAP group **`k8s-admins`** is the intended admin **`Group`** name for **`ClusterRoleBinding`** when mapping Authelia’s **`groups`** claim to RBAC (see [`.cursor/skills/flux-gitops/SKILL.md`](../flux-gitops/SKILL.md) § public hostnames).

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

| Annotation                    | Value                          | Notes                                                    |
| ----------------------------- | ------------------------------ | -------------------------------------------------------- |
| `gethomepage.dev/enabled`     | `"true"`                       | Must be string `"true"`                                  |
| `gethomepage.dev/group`       | `Applications` or `Management` | Groups in the dashboard                                  |
| `gethomepage.dev/name`        | Display name                   | Human-readable name                                      |
| `gethomepage.dev/icon`        | Icon identifier                | MDI icons (`mdi-*`) or named icons (`redis`, `homepage`) |
| `gethomepage.dev/description` | Short text                     | Shown below the name                                     |

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
5. If one Ingress fronts **multiple** Deployments (e.g. `/` + `/api` on one host), set **`gethomepage.dev/pod-selector`** so Homepage can resolve pod status (e.g. `app in (my-frontend, my-api)`). Otherwise it may infer `app` from the Ingress name and show **not found**.
6. Commit to `main`.

## Troubleshooting

- **404 on a hostname:** Verify DNS resolves to a Traefik node, the `Host` header matches the Ingress rule, and the backend Service + Endpoints exist (`kubectl get endpoints -n test <service>`).
- **CORS issues (browser OTLP):** Add Traefik CORS middleware if the web app origin differs from the OTLP ingress host. Include `traceparent`, `tracestate`, and `baggage` in `accessControlAllowHeaders` when browsers send them. Same-host path routing (e.g. UI + `/api` on one hostname) avoids CORS for those API requests; Traefik forwards inbound client headers to backends by default.
- **Blank page from chart-managed Ingress (e.g. Kubevious):** Check all pods are Running and the Service has Endpoints.
