# Prometheus Agent edge-sdr: remote_write to production

Create a Secret that Flux merges into the Helm values (only the `remote_write` URL). Do not commit this Secret.

> **Must merge into `serverFiles.prometheus.yml.remote_write`, not `server.remoteWrite`.**
> The HelmRelease already defines a full `serverFiles.prometheus.yml` (single `global`,
> `scrape_configs`, `rule_files`). Setting the chart's `server.remoteWrite` makes the
> prometheus chart emit its *own* assembled `prometheus.yml` block (chart-default `global`)
> in addition to ours — two top-level `global:` keys, which Prometheus rejects with
> `field global already set`. Injecting `remote_write` into our block keeps one `global`.

## Prerequisites

- Production applies [`prometheus-nodeport.yaml`](../../../production/apps/observability/prometheus-nodeport.yaml) (NodePort **30081**).
- Pick a production node LAN IP reachable from edge workers.

## Create the Secret

Use a **multi-line** `values.yaml` fragment (YAML):

```bash
kubectl -n prometheus-agent-edge-sdr create secret generic prometheus-agent-remote-write \
  --from-file=values.yaml=- <<'EOF'
serverFiles:
  prometheus.yml:
    remote_write:
    - url: http://10.0.0.50:30081/api/v1/write
EOF
```

Replace `10.0.0.50` with your production node IP. Path **`/api/v1/write`** is the Prometheus remote write receiver (see `enableRemoteWriteReceiver` on production kube-prometheus-stack).

## Verify

```bash
kubectl -n prometheus-agent-edge-sdr get pods -l app.kubernetes.io/name=prometheus
kubectl -n prometheus-agent-edge-sdr logs deploy/prometheus-agent-server --tail=50
```

In production Grafana, explore Prometheus and query a node metric with `cluster="edge-sdr"`, e.g. `node_memory_MemAvailable_bytes{cluster="edge-sdr"}`.
