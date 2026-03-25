---
name: k8s-observability
description: >-
  Work with the observability stack (Prometheus, Loki, Tempo, Grafana,
  OpenTelemetry Collector) in the test cluster. Use when configuring telemetry
  endpoints, adding dashboards, instrumenting apps, or troubleshooting metrics,
  logs, and traces.
---

# Observability Stack

All observability components are in `clusters/test-deployment/apps/observability/` and deploy to namespace `test`. For detailed operational notes, see `clusters/test-deployment/apps/observability/README.md`.

## Components

| HelmRelease | Chart Source | Purpose |
|---|---|---|
| `obs-prometheus` | `prometheus-community` | Metrics collection and storage |
| `obs-loki` | `grafana` | Log aggregation (SingleBinary + bundled MinIO) |
| `obs-tempo` | `grafana` | Distributed tracing backend |
| `obs-grafana` | `grafana` | Visualization (depends on the three above) |
| `obs-otel-collector` | `open-telemetry` | OTLP receiver, routes signals to backends |

HelmRepositories are defined in `clusters/test-deployment/apps/observability/helmrepositories.yaml`.

## In-Cluster Endpoints for Apps

| Signal | Endpoint |
|---|---|
| OTLP gRPC | `obs-otel-collector.test.svc.cluster.local:4317` |
| OTLP HTTP | `http://obs-otel-collector.test.svc.cluster.local:4318` |
| Prometheus OTLP (direct) | `http://obs-prometheus-server.test.svc.cluster.local/api/v1/otlp` |

Apps should send telemetry to the **OTEL Collector** (gRPC on 4317), which fans out to Prometheus, Loki, and Tempo.

## Instrumenting an App

Add these env vars to the Deployment container:

```yaml
env:
- name: OTEL_SERVICE_NAME
  value: "<app-name>"
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: "http://obs-otel-collector.test.svc.cluster.local:4317"
```

For .NET apps that need explicit trace/metric exporters:

```yaml
- name: OTEL_TRACES_EXPORTER
  value: "otlp"
- name: OTEL_EXPORTER_OTLP_PROTOCOL
  value: "grpc"
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "service.namespace=test,deployment.environment=test"
```

For browser/Vite apps, telemetry goes to the external OTLP HTTP ingress: `http://otel.kt.wsh.no/v1/traces`. This URL is baked at image build time via `VITE_OTEL_*` env vars unless the Docker entrypoint injects it at runtime.

## Grafana

### Datasources (pre-provisioned)

| Name | UID | Type | URL |
|---|---|---|---|
| Prometheus | `prometheus` | `prometheus` | `http://obs-prometheus-server.test.svc.cluster.local` |
| Loki | `loki` | `loki` | `http://obs-loki-gateway.test.svc.cluster.local` |
| Tempo | `tempo` | `tempo` | `http://obs-tempo.test.svc.cluster.local:3200` |

Loki requires `X-Scope-OrgID: foo` (multi-tenant mode); this is configured in the Grafana datasource.

### Dashboards

Two provisioning methods:

1. **grafana.com downloads** -- specify `gnetId` and `revision` in HelmRelease values under `dashboards.default`:

```yaml
dashboards:
  default:
    my-dashboard:
      gnetId: 12345
      revision: 1
      datasource: Prometheus
```

2. **Custom JSON from repo** -- add the JSON file to `clusters/test-deployment/apps/observability/dashboards/`, then add it to the `configMapGenerator` in `clusters/test-deployment/apps/observability/kustomization.yaml`:

```yaml
configMapGenerator:
  - name: grafana-dashboard-<name>
    files:
      - dashboards/<name>.json
    options:
      disableNameSuffixHash: true
```

Then reference it in the Grafana HelmRelease under `dashboardsConfigMaps`:

```yaml
dashboardsConfigMaps:
  custom: grafana-dashboard-<name>
```

Custom dashboards appear under the **Custom** folder in Grafana.

### Login

User `admin`, password auto-generated in Secret `obs-grafana` (or set `adminPassword` in HelmRelease values).

## Service Graphs (Tempo + Prometheus)

Tempo's metrics generator derives service graph edges from traces and remote-writes them to Prometheus (`web.enable-remote-write-receiver` is enabled on the Prometheus server). In Grafana, the Tempo datasource has `serviceMap.datasourceUid: prometheus` so **Explore -> Tempo -> Service graph** works once traces exist.

Apps must export OTLP traces with a stable `service.name` for edges to appear.

## Key Operational Notes

- **Grafana 404 after deploy:** It installs last (depends on Prometheus, Loki, Tempo). Wait for all three to be Ready: `kubectl get helmrelease -n test`.
- **Empty dashboards:** Verify `extraScrapeConfigs` for the collector metrics job is at the **root** of Prometheus chart values (not nested under `server`).
- **Loki OTLP ingest:** The OTEL Collector exports logs via `otlphttp` to `http://obs-loki-gateway.test.svc.cluster.local/otlp`. The legacy `loki` exporter was removed upstream; do not use it.
- **No PVCs:** This cluster may lack a StorageClass. Persistence is disabled; data does not survive pod restarts. For production, add a StorageClass and re-enable persistence in the HelmRelease values.
- **Node exporter disabled:** `prometheus-node-exporter` is off to avoid hostPort 9100 conflicts with Traefik's hostNetwork.
