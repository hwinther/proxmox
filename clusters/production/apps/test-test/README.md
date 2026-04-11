# Test application (`test.test.wsh.no`)

Named **test** after the repo’s sample app, not after the cluster. It runs on the **production k0s cluster**, but **`*.test.wsh.no`** is the test-tier DNS zone (same workload as [`clusters/test-deployment/apps/`](../../../test-deployment/apps/), `ghcr.io/hwinther/test/*`).

| Item | Value |
|------|--------|
| Namespace | **`test-test`** (app-environment: **test** + **test**) |
| URL | **https://test.test.wsh.no** — UI on `/`; **`/api/...`** → API Service (path passed through). |
| OTLP (browser) | `https://otel.mgmt.wsh.no/v1/traces` (CORS allowlist includes this origin) |
| OTLP (API pod) | Same as compose: `OTEL_EXPORTER_OTLP_ENDPOINT` → `http://obs-otel-collector.observability-production.svc.cluster.local:4317`, `OTEL_SERVICE_NAME`=`WebApi`, `OTEL_EXPORTER_OTLP_PROTOCOL`=`grpc`, `OTEL_TRACES_EXPORTER`=`otlp`. |
| SQL / RabbitMQ (API) | Matches compose **`ConnectionStrings__Blogging`** and **`RabbitMq__*`** using short hostnames **`sqlserver`** and **`rabbitmq`** — deploy **`Service`s with those names** in **`test-test`** (SQL on **1433**, AMQP on **5672**) or patch the connection string / host envs. SA password is the compose dev value; prefer a **Secret** for real use. |
| Redis (frontend) | Shared test-tier in **`shared-test`**: `REDIS_HOST`=`redis.shared-test.svc.cluster.local`, `REDIS_PORT`=`6379` — see [`../shared/README.md`](../shared/README.md). |

DNS: ensure **`test.test.wsh.no`** resolves like other `*.test.wsh.no` names (edge nginx already matches `*.test.wsh.no` in [`templates/nginx/internal-reverse-proxy.conf`](../../../templates/nginx/internal-reverse-proxy.conf)).

The separate **test-deployment** cluster still uses `test.kt.wsh.no` / `api.kt.wsh.no`; this copy does not replace that environment.

If you previously applied the old **`test`** namespace from this repo, remove it after Flux reconciles **`test-test`**: `kubectl delete namespace test` (only if nothing else uses that namespace on this cluster).
