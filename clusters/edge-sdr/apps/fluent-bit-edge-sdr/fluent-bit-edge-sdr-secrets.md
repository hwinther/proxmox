# Fluent Bit edge-sdr: Loki endpoint secret

Committed manifests do not include a Kubernetes `Secret` (see repo `AGENTS.md`). Create the secret on the **edge-sdr** cluster after the production Loki gateway is reachable via NodePort.

## Prerequisites

- Production applies `obs-loki-gateway-nodeport` (NodePort **30080**) and Flux has reconciled it.
- Pick any production node LAN IP that accepts cluster NodePort traffic (NLLB + Cilium).

## Create the secret

```bash
kubectl -n fluent-bit-edge-sdr create secret generic fluent-bit-loki-endpoint \
  --from-literal=LOKI_HOST=10.0.0.50 \
  --from-literal=LOKI_PORT=30080
```

Replace `LOKI_HOST` with your production node IP. `LOKI_PORT` must match the NodePort in [`clusters/production/apps/observability/loki-gateway-nodeport.yaml`](../../../production/apps/observability/loki-gateway-nodeport.yaml).

## Verify

```bash
kubectl -n fluent-bit-edge-sdr get pods -l app.kubernetes.io/name=fluent-bit
kubectl -n fluent-bit-edge-sdr logs daemonset/fluent-bit --tail=50
```

In Grafana (production Loki datasource, org header `foo`), query: `{cluster="edge-sdr"}`.
