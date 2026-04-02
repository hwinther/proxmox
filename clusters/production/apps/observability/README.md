# Observability stack (production)

Namespace: **`observability-production`**. Flux installs **kube-prometheus-stack** (Prometheus Operator, Prometheus with OTLP + remote-write receiver, Grafana, Alertmanager, node-exporter, kube-state-metrics), **Loki** (SingleBinary + MinIO on Ceph), **Tempo** (Ceph PVC), and the **OpenTelemetry Collector** (contrib).

## Prerequisites

- **Ceph RBD** StorageClass `ceph-rbd` and secret `csi-rbd-secret` (see [`../ceph-csi/`](../ceph-csi/README.md)).
- **DNS** for management ingresses: `grafana.mgmt.wsh.no`, `otel.mgmt.wsh.no`, `alertmanager.mgmt.wsh.no` (see [`../../README.md`](../../README.md)).

## In-cluster endpoints (apps)

| Signal | Endpoint |
|--------|----------|
| OTLP gRPC | `obs-otel-collector.observability-production.svc.cluster.local:4317` |
| OTLP HTTP | `http://obs-otel-collector.observability-production.svc.cluster.local:4318` |
| OTLP HTTP (via ingress) | `https://otel.mgmt.wsh.no` (path `/v1/traces`, etc.) |
| Prometheus | `http://obs-kps-kube-prometheus-st-prometheus.observability-production.svc.cluster.local:9090` |

## Grafana

- **Ingress:** `grafana.mgmt.wsh.no` → Service `obs-kps-grafana:80`.
- **Login:** user `admin`; password in Secret `obs-kps-grafana` (chart-generated unless set in values).
- **Datasources:** Prometheus (default from stack), Loki, Tempo (see `kube-prometheus-stack-helmrelease.yaml` `grafana.additionalDataSources`).
- **Dashboards:** stock kube-prometheus-stack Grafana dashboards (phase 1; no extra gnet IDs in Git).

## Helm releases

| HelmRelease | Purpose |
|-------------|---------|
| `obs-kps` | kube-prometheus-stack |
| `obs-loki` | Loki + gateway + MinIO |
| `obs-tempo` | Tempo + metrics generator → Prometheus remote_write |
| `obs-otel-collector` | OTLP → Tempo / Loki / Prometheus OTLP |

## OTel collector metrics

Prometheus scrapes the collector self-metrics via **additionalServiceMonitors** in `obs-kps` (Service port name `metrics`, `:8888`).

## CORS (browser OTLP)

Middleware `otel-cors` in this namespace; allowlist includes `https://clutterstock.wsh.no`. Extend `observability-ingress.yaml` for more origins.
