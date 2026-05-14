---
name: k8s-observability
description: >-
  Work with the observability stack (Prometheus, Loki, Tempo, Grafana,
  OpenTelemetry Collector) on test or production clusters in this repo. Use when
  configuring telemetry endpoints, adding dashboards, instrumenting apps, or
  troubleshooting metrics, logs, and traces.
---

# Observability Stack

## Production (`clusters/production/apps/observability/`)

Namespace **`observability-production`**. **kube-prometheus-stack** HelmRelease **`obs-kps`** provides Prometheus (with OTLP + remote-write receiver), Grafana (bundled), Alertmanager, node-exporter, and kube-state-metrics. Separate HelmReleases: **`obs-loki`**, **`obs-tempo`**, **`obs-otel-collector`**.

Operational notes: [`clusters/production/apps/observability/README.md`](../../../clusters/production/apps/observability/README.md).

### Production in-cluster endpoints

| Signal | Endpoint |
|--------|----------|
| OTLP gRPC | `obs-otel-collector.observability-production.svc.cluster.local:4317` |
| OTLP HTTP | `http://obs-otel-collector.observability-production.svc.cluster.local:4318` |
| OTLP HTTP (ingress) | `https://otel.mgmt.wsh.no` |
| Prometheus | `http://obs-kps-kube-prometheus-st-prometheus.observability-production.svc.cluster.local:9090` |

### Production Grafana

- Ingress: **`grafana.mgmt.wsh.no`** → `obs-kps-grafana:80`.
- Secret: **`obs-kps-grafana`** (admin password).
- Extra datasources (Loki, Tempo) are set in **`kube-prometheus-stack-helmrelease.yaml`** under `grafana.additionalDataSources`.

## Instrumenting an App

Send telemetry to the **OTEL Collector** (gRPC **4317**) for the target cluster/namespace.

**Production example:**

```yaml
env:
  - name: OTEL_SERVICE_NAME
    value: "<app-name>"
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://obs-otel-collector.observability-production.svc.cluster.local:4317"
```

**Browser / Vite (production):** use the OTLP HTTP ingress, e.g. **`https://otel.mgmt.wsh.no/v1/traces`** (CORS allowlist and headers—including W3C trace context—in `observability-ingress.yaml`). Same-origin app API traffic (e.g. `/api` on the app host) does not use this CORS path for fetch propagation.

## Service graphs (Tempo + Prometheus)

Tempo’s metrics generator **remote_writes** to Prometheus (`/api/v1/write`). In Grafana, the Tempo datasource uses **`serviceMap.datasourceUid: prometheus`** so **Explore → Tempo → Service graph** works when traces and metrics exist.

## Operational notes

- **Empty collector dashboards:** On production, collector self-metrics are scraped via **kube-prometheus-stack `additionalServiceMonitors`** (port **`metrics`**, target `:8888`). On test, ensure **`extraScrapeConfigs`** for the collector remains at the **root** of the Prometheus chart values.
- **Loki OTLP:** Collector uses **`otlphttp`** to the Loki gateway **`/otlp`** path with header **`X-Scope-OrgID: foo`** (matches Grafana Loki datasource).
- **Persistence:** Production uses **ceph-rbd** for Prometheus, Grafana, Loki/MinIO, Tempo, and Clutterstock SQLite where configured; test may use `local-path` or emptyDir.
