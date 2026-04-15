# Prometheus Agent (edge-sdr)

[Helm chart](https://github.com/prometheus-community/helm-charts/tree/main/charts/prometheus): single **Deployment** in **agent mode** (no local TSDB), scrapes **node-exporter** in `node-exporter-edge-sdr`, **remote_writes** to production Prometheus.

- **Scheduling:** no toleration for `node-type=edge-sdr`, so the pod stays off tainted Pis; node-exporter DaemonSet still runs on Pis and is scraped via the Service endpoints.
- **Secret:** create `prometheus-agent-remote-write` before the HelmRelease can succeed ([`prometheus-agent-edge-sdr-secrets.md`](./prometheus-agent-edge-sdr-secrets.md)).
- **Production:** Prometheus is exposed on the LAN with NodePort **30081** ([`prometheus-nodeport.yaml`](../../../production/apps/observability/prometheus-nodeport.yaml)).
