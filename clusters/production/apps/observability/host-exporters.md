# Host exporters on the bare-metal Proxmox / PBS hosts

The physical hosts run two Prometheus exporters as **plain systemd services** (not Kubernetes — the
hosts are outside the cluster). Prometheus scrapes them via static jobs in
[`kube-prometheus-stack-helmrelease.yaml`](kube-prometheus-stack-helmrelease.yaml)
(`prometheusSpec.additionalScrapeConfigs`):

| Exporter           | Port  | Scrape job          | Alerts / dashboard                                         |
| ------------------ | ----- | ------------------- | ---------------------------------------------------------- |
| smartctl_exporter  | 9633  | `smartctl`          | `prometheusrule-smartctl.yaml`, `dashboards/disk-health.json` |
| node-exporter      | 9100  | `node-exporter-pve` | stock `Node*` rules + `prometheusrule-node-temp.yaml` (CPU temp); dashboards `proxmox-hosts.json` + stock "Node Exporter / Nodes" |

Hosts and their `node` label (the scrape job sets `instance` = this name):

| Host             | IP          | Role                                  |
| ---------------- | ----------- | ------------------------------------- |
| `office-pve-amd` | 10.20.4.18  | PVE + Ceph OSD (AMD, `k10temp`)       |
| `office-pve-i9`  | 10.20.4.20  | PVE + Ceph OSD (Intel, `coretemp`)    |
| `shuttle01`      | 10.20.4.34  | PVE + Ceph OSD                        |
| `shuttle02`      | 10.20.4.35  | PVE (not a Ceph node)                 |
| `shuttle03`      | 10.20.4.36  | PVE (not a Ceph node), joined 2026-11 |
| `pbs-ks`         | 10.30.0.6   | Standalone PBS, KS site (over link)   |

## Why node-exporter on the hosts

The kube-prometheus-stack ships ~25 `Node*` rules (filesystem fill, CPU, memory, clock sync, NIC
RX/TX errors, systemd unit failures, conntrack, RAID), but they only match series with
`job="node-exporter"`. Without a host exporter those rules cover **only the k0s VMs and edge Pis** —
the hypervisors themselves were monitored for disk SMART and nothing else. The `node-exporter-pve`
job is **relabeled to `job=node-exporter`** so the existing rules and the stock Grafana
"Node Exporter / Nodes" dashboards pick up the bare metal with no new rules (the one exception is
x86 CPU/package temperature, which the default set doesn't cover — added in
`prometheusrule-node-temp.yaml` as `NodeCpuOverheating`).

## Install (per host)

Debian-based (Proxmox VE and Proxmox Backup Server both qualify):

```bash
apt-get update && apt-get install -y prometheus-node-exporter lm-sensors prometheus-smartctl-exporter
# hwmon CPU temps: make sure the right driver is loaded so node_hwmon_temp_celsius is populated
sensors-detect --auto        # loads coretemp (Intel) or k10temp (AMD); persists to /etc/modules
systemctl enable --now prometheus-node-exporter
# prometheus-smartctl-exporter starts itself on install (:9633); its unit is not named after the
# package, so find it with: systemctl list-units '*smartctl*'
# verify locally
curl -s localhost:9100/metrics | grep -E '^node_hwmon_temp_celsius' | head
curl -s localhost:9633/metrics | grep -c '^smartctl_device'
```

The Debian package enables a sensible default collector set (incl. `hwmon`, `systemd`, `filesystem`,
`netdev`). No extra flags needed; if you install the upstream tarball instead, run it with at least
`--collector.hwmon --collector.systemd` and a matching unit file.

## Firewall (per host)

Each host must allow the cluster subnet to **both** exporter ports — `:9633` (smartctl) and `:9100` (node-exporter). Add an IN ACCEPT rule per port:

```bash
# /etc/pve/firewall/<node>.fw  (or the host firewall GUI):
#   IN ACCEPT  from 10.20.13.0/24  to tcp/9633   # smartctl_exporter
#   IN ACCEPT  from 10.20.13.0/24  to tcp/9100   # node-exporter
```

`pbs-ks` is reached over the site link; open both ports there the same way.

## Verify end-to-end

```bash
# from a k0s node (has cluster-subnet source IP):
for ip in 10.20.4.18 10.20.4.20 10.20.4.34 10.20.4.35 10.30.0.6; do
  echo -n "$ip "; curl -s -o /dev/null -w '%{http_code}\n' http://$ip:9100/metrics; done

# from Prometheus (NodePort :30081) after Flux reconciles the scrape config:
#   up{job="node-exporter"}                         -> now includes the 5 hosts
#   node_filesystem_avail_bytes{instance="shuttle01"} -> Node* rules now evaluate for the host
#   node_hwmon_temp_celsius{instance="office-pve-amd"} -> confirm the CPU sensor labels
```

**CPU-temp selector (resolved):** `NodeCpuOverheating` matches CPU chips via a `node_hwmon_chip_names`
join (`chip_name=~"coretemp|k10temp"`), not the `chip` label — Intel exposes `platform_coretemp_0`,
but AMD k10temp shows up under a PCI-address chip (`pci0000:00_0000:00:18_3`), so a chip-label regex
silently misses the AMD host. The join also keeps NVMe sensors out (they read 80°C+ and are covered
by `SmartNvmeOverheating`). Verified live on office-pve-amd + office-pve-i9. Dry-run rule changes
server-side before pushing: `kubectl apply --dry-run=server -f prometheusrule-node-temp.yaml`.

## Edge VPSes (abyss, dns-master)

The two VPSes are reached over the WireGuard tunnel (10.31.0.2 = abyss, 10.31.0.3 = dns-master).
Their logs already reach Loki (`{host="abyss"}`, `{host="dns-master"}`); these exporters add
metrics. Scrape jobs: `node-exporter-vps` (relabeled to `job="node-exporter"`) and `bind`.

```bash
apt install prometheus-node-exporter prometheus-bind-exporter
# bind both exporters to the tunnel IP only (10.31.0.3 on dns-master):
#   /etc/default/prometheus-node-exporter:  ARGS="--web.listen-address=10.31.0.2:9100"
#   /etc/default/prometheus-bind-exporter:  ARGS="--bind.stats-url=http://127.0.0.1:8053/ --web.listen-address=10.31.0.2:9119"
# named statistics channel: a TOP-LEVEL statement (not inside options { }), e.g. in named.conf.local:
#   statistics-channels { inet 127.0.0.1 port 8053 allow { 127.0.0.1; }; };
named-checkconf && systemctl reload named
systemctl restart prometheus-node-exporter prometheus-bind-exporter
```

Firewall: tcp/9100 and tcp/9119 from the cluster must be allowed on each VPS's wg interface and in
the OPNsense rule towards the tunnel (the same path the CrowdSec :6060/:60601 scrapes use).

Verify: `up{job=~"node-exporter|bind", instance=~"abyss|dns-master"}` and `bind_up`.
