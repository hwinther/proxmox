# node-exporter (edge-sdr)

DaemonSet from [prometheus-community/prometheus-node-exporter](https://github.com/prometheus-community/helm-charts) exposes host metrics on **TCP 9100** via the `prometheus-node-exporter` Service in this namespace.

- **hostNetwork** is disabled so it does not collide with Traefik on the edge cluster.
- Default chart tolerations schedule onto **tainted** SDR nodes (`node-type=edge-sdr`) as well as untainted workers.

Metrics are **remote_written** to production Prometheus by [prometheus-agent-edge-sdr](../prometheus-agent-edge-sdr/) (see `prometheus-agent-edge-sdr-secrets.md` for the endpoint Secret). Production exposes Prometheus on **NodePort 30081** ([`prometheus-nodeport.yaml`](../../../production/apps/observability/prometheus-nodeport.yaml)).
