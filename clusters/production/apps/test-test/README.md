# Test application (`test.test.wsh.no`)

Named **test** after the repo’s sample app, not after the cluster. It runs on the **production k0s cluster**, but **`*.test.wsh.no`** is the test-tier DNS zone (same workload as [`clusters/test-deployment/apps/`](../../../test-deployment/apps/), `ghcr.io/hwinther/test/*`).

| Item | Value |
|------|--------|
| Namespace | **`test-test`** (app-environment: **test** + **test**) |
| URL | **https://test.test.wsh.no** — UI on `/`; browser calls **`/api/...`** (Traefik **StripPrefix** `/api` so the API pod still sees root paths like on `api.kt.wsh.no`). If the API is changed to serve only under `/api` in-process, remove the `test-api-stripprefix` middleware and the `test-api` Ingress annotation that references it. |
| OTLP (browser) | `https://otel.mgmt.wsh.no/v1/traces` (CORS allowlist includes this origin) |
| OTLP (API pod) | `obs-otel-collector.observability-production:4317` |

DNS: ensure **`test.test.wsh.no`** resolves like other `*.test.wsh.no` names (edge nginx already matches `*.test.wsh.no` in [`templates/nginx/internal-reverse-proxy.conf`](../../../templates/nginx/internal-reverse-proxy.conf)).

The separate **test-deployment** cluster still uses `test.kt.wsh.no` / `api.kt.wsh.no`; this copy does not replace that environment.

If you previously applied the old **`test`** namespace from this repo, remove it after Flux reconciles **`test-test`**: `kubectl delete namespace test` (only if nothing else uses that namespace on this cluster).
