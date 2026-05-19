# Cilium LB-IPAM + L2 announcements

Cluster-scoped Cilium CRs that turn `Service type: LoadBalancer` into a real,
ARP-reachable VIP on the node L2 (`10.20.13.0/24`) — no MetalLB.

- **`ciliumloadbalancerippool.yaml`** — the assignable VIP range. Currently a
  single address reserved for the MQTT broker.
- **`ciliuml2announcementpolicy.yaml`** — makes Cilium ARP-announce LB VIPs on
  `eth0`. One node is elected per service (k8s Lease) with automatic failover.

## Prerequisite (NOT GitOps)

L2 announcements must be enabled in the **Cilium Helm stanza in k0s** — it is
**not** a manifest in this repo. Required keys in `/etc/k0s/k0s.yaml` on every
controller (then a gated rolling reconcile, see `infra/k0s/cilium-k0s-setup.md`):

```yaml
          l2announcements:
            enabled: true
          k8sClientRateLimit:
            qps: 10
            burst: 20
```

Verify after reconcile:

```bash
kubectl -n kube-system get cm cilium-config -o jsonpath='{.data.enable-l2-announcements}'
# -> true
```

LB-IPAM itself is already enabled in this Cilium build (`enable-lb-ipam=true`),
so the pool below assigns immediately; without the L2 prerequisite the VIP is
assigned but unreachable.

## VIP

`10.20.13.100` — reserved here for `mosquitto-production/mosquitto`. Must stay
outside the DHCP range and unused elsewhere. IoT/ESP clients on other VLANs
reach it via normal L3 routing (router/firewall must permit
`<iot-subnet> -> 10.20.13.100:1883`).
