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

### Where are the Deployments?

In **`obs-loki`**, the Loki **SingleBinary** process is a **StatefulSet** named **`obs-loki`**, not a Deployment. You should see **`obs-loki-gateway`** as a **Deployment**, plus StatefulSets **`obs-loki`**, **`obs-loki-minio`**, **`obs-loki-results-cache`**. Use:

`kubectl get deploy,sts,pods -n observability-production`

**kube-prometheus-stack** also creates many **StatefulSets** (Prometheus, Alertmanager) and **DaemonSets** (node-exporter), not only Deployments.

## OTel collector metrics

Prometheus scrapes the collector self-metrics via **additionalServiceMonitors** in `obs-kps` (Service port name `metrics`, `:8888`).

## CORS (browser OTLP)

Middleware `otel-cors` in this namespace; allowlist includes `https://clutterstock.wsh.no`. Extend `observability-ingress.yaml` for more origins.

## Homepage (`mgmt.wsh.no`)

- **Kubernetes widget** (cluster/node CPU and memory) needs the **metrics.k8s.io** API. k0s ships **metrics-server** in `kube-system` by default — do **not** install a second copy via Helm (name collisions / reconcile failures). If `kubectl top nodes` works, the widget should too; if metrics scrape fails, patch the k0s **metrics-server** Deployment args (e.g. `--kubelet-insecure-tls`) per [`infra/k0s/cilium-k0s-setup.md`](../../../infra/k0s/cilium-k0s-setup.md).
- **Ingress-derived pod status** uses pod labels. For the OpenTelemetry ingress, **`gethomepage.dev/pod-selector`** must match the collector pods (e.g. `app.kubernetes.io/instance=obs-otel-collector`), not the Ingress resource name.
