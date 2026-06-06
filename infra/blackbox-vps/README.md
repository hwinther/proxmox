# External blackbox-exporter (VPS)

An off-cluster [blackbox-exporter](https://github.com/prometheus/blackbox_exporter) that probes the
public `*.wsh.no` endpoints from an **internet vantage point**, so failures on the real public path
(external DNS → internet → nginx TLS front-end) are caught — the class of user-facing outage that
in-cluster metrics can't see (e.g. the front-end response-truncation incident).

The cluster Prometheus scrapes this exporter **over the existing tunnel** and turns probe results into
alerts. The probe targets, modules, and alert rules live in the cluster repo:

- Probes: [`clusters/production/apps/observability/blackbox-probes.yaml`](../../clusters/production/apps/observability/blackbox-probes.yaml)
- Alerts: [`clusters/production/apps/observability/prometheusrule-blackbox.yaml`](../../clusters/production/apps/observability/prometheusrule-blackbox.yaml)

## Why off-cluster

An in-cluster blackbox would egress and (via DNS/NAT hairpin) re-enter through the internal ingress,
bypassing the public front-end — so it can't observe what an internet user actually experiences. This
instance sits outside, on the far side of the front-end.

## Deploy on the VPS

1. Copy this directory (`docker-compose.yml`, `blackbox.yml`) to the VPS.
2. Set the tunnel IP (the VPS's address on the tunnel the cluster uses), e.g.:
   ```bash
   echo "TUNNEL_IP=10.10.0.2" > .env      # <- the VPS's tunnel interface IP
   docker compose up -d
   ```
   The published port binds to `${TUNNEL_IP}:9115` only — reachable from the cluster over the tunnel,
   **not** from the public internet. Do not bind to `0.0.0.0`.
3. Confirm it's serving locally and over the tunnel:
   ```bash
   curl -s 'http://127.0.0.1:9115/-/healthy'
   curl -s 'http://127.0.0.1:9115/probe?target=https://clutterstock.wsh.no&module=http_2xx' | grep probe_success
   ```

## Wire up the cluster side

Put the **same** `TUNNEL_IP` into both Probes' `prober.url` (replace the `10.0.0.0-PLACEHOLDER:9115`
placeholder) in `blackbox-probes.yaml`, then commit. After Flux reconciles, verify in Prometheus:

```promql
probe_success{probe_origin="vps-external"}
probe_ssl_earliest_cert_expiry{probe_origin="vps-external"}
```

## Firewall / security

- The cluster must reach `TUNNEL_IP:9115` over the tunnel (allow that on the VPS).
- The exporter must **not** be exposed publicly — binding to the tunnel IP handles this; double-check
  the VPS firewall does not forward `:9115` from the public interface.
- blackbox is unauthenticated by design; the tunnel + interface binding is the access control.

## Modules

| Module | Used for | Pass criteria |
|---|---|---|
| `http_2xx` | `clutterstock.wsh.no`, `www.wsh.no` | HTTP 2xx + valid TLS |
| `http_public` | auth-gated / redirecting services (`auth`, `ddns`, `ddnsadmin`, `node-red`, `home-assistant`, `rabbitmq`, `pbs`) | HTTP 200/3xx/401/403 + valid TLS (fails on 5xx/TLS/timeout) |

Re-bucket hosts between the two Probes as you learn each endpoint's real unauthenticated response.
`*.mgmt.wsh.no` is intentionally **not** probed — it resolves to LAN IPs and is unreachable externally.
