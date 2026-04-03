# Internal reverse proxy → k0s (wsh.no)

This doc matches [`internal-reverse-proxy.conf`](internal-reverse-proxy.conf). Edit that file when node IPs change.

## What listens on port 8000

| Upstream pool | Intended backend | Why the IP is stable |
|---------------|------------------|----------------------|
| **wsh_general** | **Traefik** on the production k0s cluster | Flux [`traefik-helmrelease.yaml`](../../clusters/production/apps/traefik/traefik-helmrelease.yaml): `DaemonSet`, **`hostNetwork: true`**, HTTP entry on **port 8000**. Every node runs Traefik on its **own LAN IP**, not on “the node where the app pod landed.” |
| **wsh_kt** | KT / mgmt-kt stack | Treated as a **fixed** endpoint (e.g. dedicated VM or separate ingress). If that stack moves to the same Traefik pattern, add **all** of its node IPs to `upstream wsh_kt` the same way as `wsh_general`. |

Do **not** point nginx at a Kubernetes **ClusterIP** (`10.96.0.0/12`) from a host outside the cluster unless you have explicit routing into the service network.

## Failure behavior

- **`least_conn`** sends new connections to the upstream with the fewest active connections (among healthy servers).
- **`max_fails=3`** and **`fail_timeout=30s`**: after 3 failed probes in the window, nginx marks the server **down** for 30s, then retries. Adjust if your health checks need different sensitivity.
- **`backup`** (optional on a `server` line): used only when all non-backup servers are down.

## Operations checklist

1. After **adding or removing k0s nodes**, update **`upstream wsh_general`** with every node IP that should receive traffic on **8000**.
2. Run **`nginx -t`** and reload nginx.
3. Optional: use **internal DNS** (multiple A records) instead of listing IPs, resolving to the same node set—behavior is similar if all names resolve to the same pool.

## Alternatives (not in the template)

- **VIP (e.g. Keepalived)** in front of a subset of nodes: nginx targets one IP; failover is handled outside nginx.
- **`LoadBalancer` + MetalLB / Cilium LB / kube-vip**: one stable IP for a `Service`; use if Traefik is **not** host-network on every node.
- **NodePort**: nginx uses `any_node:high_port` with the same multi-node or VIP idea.

If TLS and routing can live entirely on the cluster, you can point clients at Traefik (or a single LB VIP) and **drop** this nginx hop for those hostnames.

## Tracing headers (W3C Trace Context)

This template does **not** strip client request headers. Nginx forwards them to Traefik by default, including **`traceparent`**, **`tracestate`**, and **`baggage`**. You only need extra `proxy_set_header` lines if you add middleware that removes unknown headers or build an allowlist of forwarded headers.
