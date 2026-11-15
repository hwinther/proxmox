---
name: homelab-alert-triage
description: Triage a firing alert or odd symptom in the homelab (k0s production/edge clusters, Proxmox hosts, Ceph, CNPG, edge WAF, game probes) against the known causes and false alarms before digging. Use when an Alertmanager/Prometheus alert fires, a dashboard looks wrong, something "is down", backups silently stop, or the user asks "why is X alerting".
---

# Homelab alert triage

Most alerts here have a known cause, and several are known false alarms. **Match the symptom against the table before investigating**, then confirm with the listed check. Don't "fix" anything until the check confirms it. The user sometimes runs several agents at once, so an unexpected cluster change may be intentional. Ask before reverting it.

## Ground rules

- **DNS proves nothing.** Internal DNS has a wildcard, so every name resolves. Confirm a host by IP plus a service answering on its port.
- **Test the path you claim.** On multi-homed hosts, binding a source IP doesn't choose the egress interface (use `SO_BINDTODEVICE` or `curl --interface <dev>`). Judge UDP reachability with something that round-trips (STUN/3478, NTP), never a one-way capture.
- **Freshly rebooted hosts look clean.** Some faults scale with uptime.
- Query Prometheus at 30-second steps for intermittent stalls. Five-minute steps average the spikes away.
- Changes go through git. Live `kubectl` edits to Flux-owned fields get reverted on the next reconcile.

## Known causes and false alarms

| Symptom | Likely cause | Confirm with | Action |
|---|---|---|---|
| `KubeAggregatedAPIDown` for **several** APIs at once (metrics.k8s.io and kubescape) | konnectivity agents rolled because a controller's lease flapped, from etcd slow-disk stalls on a controller VM | konnectivity-agent DaemonSet generation and ControllerRevisions differ only in server count; etcd "heartbeat ... slow disk" in the controller's k0s log | Not netpol and not the apps. The long-term fix is controller disks on local SSD. A Cilium restart also gives 2–4 minutes of this. |
| `NodeDiskIOSaturation`: huge aqu-sq and seconds of await, but util low | PVE kernel 7.0.14-x **bogus disk-time accounting** (32-bit ms wrap, a write charged since boot) | `rate(node_disk_io_time_weighted_seconds_total[5m])*300/(node_time_seconds-node_boot_time_seconds)` ≈ **1.11**; PSI io `full` near 0; `node_disk_io_now` 0 | Ignore. No fixed kernel known; don't pin back. |
| Game external probes (`*UnreachableFromInternet`, `ExternalEndpointDown`, VPS `TargetDown`) | **Game server hibernated** (STS at 0/0) | `kubectl get sts -n <game>-production` | Expected noise. |
| Game external probes: **all** fail, scrape duration ≈ timeout | **Stale DDNS** after a WAN IP change | Compare the dynamic DDNS record (asked of its authoritative server) with the current egress IP | Ask the user who updates the record, fix it, then restart the probe exporters on the VPS. |
| Game probes **flap**, exporter logs "Unsupported protocol header", fails *faster* than success | **Duplicated UDP replies** on the office-pve-i9 path (r8169 offload) | tcpdump at the exporter shows two replies per query | `ethtool -K <nic> gro off gso off tso off` on the host, **then restart the exporters**, because they don't recover by themselves. |
| Cross-node pod networking broken on some nodes (DNS/TCP fail, ping works) | **Realtek r8169 VXLAN checksum offload** on office-pve-i9 | Which PVE host the node runs on (`qm list`) | Disable offloads on the uplink and persist them. Don't chase Cilium, MTU or identity. |
| `*-pbs-backup` pods Pending; backups silently stop | Node short on CPU or memory **requests** (common after reboots), or a big-request squatter on the 2-core node | `kubectl describe node <n>` Allocated resources; `kubectl get jobs -A \| grep -v Complete` | Move Deployment pods off the node (see k0s-node-maintenance rebalance). **Never change the backup affinity.** |
| Backup Job Complete but tiny or fast | Backup runs as root without caps, so mode-0600 files are skipped | Job log contains `access denied` | Set the CronJob `runAsUser` to the app's uid. |
| `KubeJobFailed` on a "one-time" Job, recurring daily | **Flux + `ttlSecondsAfterFinished`** re-creates it | `kube_job_created{job_name=...}` over 10 days | Remove the TTL; re-run by renaming. |
| Flux Kustomization fails dry-run: Kyverno "missing digest" | `verifyDigest: true` on an unchanged image | A fresh pod with the same image is admitted and mutated | `verifyDigest: false`, keep `mutateDigest`. Never re-sign images for this. |
| Whole Flux apply failing after a PrometheusRule change | Invalid template function (`lower`) rejected by the webhook | `kubectl apply --dry-run=server -f <rule>` | Use `toLower`/`toUpper`. |
| Flux alerts never fire | Flux 2.8 has no `gotk_reconcile_condition` | `count(gotk_reconcile_condition)` empty | Use `gotk_resource_info` (ksm-flux) or `controller_runtime_reconcile_total`. |
| New scrape target `down` or `up=0` but the exporter is fine | Default-deny ingress, no Prometheus allowance | Hubble `POLICY_DENIED` to that port | Add an ingress rule from Prometheus. |
| Pod crash-loops with **empty logs**, killed at ~30s | Netpol floor blocks apiserver egress (latent until restart) | `hubble observe --pod ns/name` shows a drop to :6443 | Add the pod to the namespace's apiserver-egress CNP. |
| Every `*.mgmt.wsh.no` dead, cluster healthy | The mgmt nginx front-end box is down (outside the cluster) | `curl -H 'Host: mgmt.wsh.no' http://<node>:8000/` works | Power or fix that box. |
| Large assets cut at ~128 KB (`ERR_CONTENT_LENGTH_MISMATCH`; Grafana "failed to load application files") | mgmt nginx `proxy_temp` disk full | In-pod size vs proxied size of one asset | Free disk on that box. |
| Login at auth.wsh.no blocked with a WAF page, **zero** attempts in the Authelia log | OPNsense **NAXSI** rule on a URL in a POST body (`targetURL`, `uri`, `redirect`) | OPNsense Nginx HTTP error log `NAXSI_FMT ... id0=1101&var_name0=...` | Scoped whitelist for that URL and argument, attached to the policy. Expect one rule group per retest. Same class for free-text bodies, CSP reports and `/__manifest`. |
| `NodeSystemdServiceFailed` `zfs-volume-wait` | One zvol missed its udev link (boot race) | `zfs list -t volume` vs `ls /dev/zvol/<pool>`; the orphan `/dev/zdN` is `root:root 0600` | `udevadm trigger --action=change /sys/block/zdN`, then restart the unit (user runs it). |
| ceph-mgr high CPU in `msgr-worker` threads | Stale rotating service keys ("could not get service secret") | `top -H -p <mgr pid>`; grep the mgr log | `ceph mgr fail <name>`. Never `--wipe-rotating-keys`. |
| kubescape `storage` ~600m CPU | Normal (aggregated API with all node-agents writing to it) | Spikes far above → a redeploy conflict storm | Requests are already sized; narrow its scope if it recurs. |
| PVE upgrade hangs at "Setting up pve-manager" on a test node | Lone node not quorate | `pvecm status`, `systemctl list-jobs` | `pvecm expected 1` while the others are really off. |
| `kubectl logs -f` "too many open files" | Node inotify limit 128 | `sysctl fs.inotify.max_user_instances` | sysctl.d file with 8192/524288 (user runs it). |
| NFS mounts fail on *some* nodes ("Connection refused", exit 255) | Kernel/module mismatch after `apk upgrade` (no nfsv4 module) | `uname -r` vs `ls /lib/modules`; `lsmod \| grep nfs` | Reboot the node, or move pods to a node with nfsv4 loaded. |
| Pods stuck ContainerCreating "rbd image ... is still being used" after drains | Stale kernel rbd mapping on the old node | `rbd status <pool>/<image>` watcher | `echo N > /sys/bus/rbd/remove_single_major` on the old node (user runs it). |
| Namespace stuck Terminating, `NamespaceDeletionDiscoveryFailure` on kubescape | ceph-csi nodeplugin missing on a node, so kubescape storage down; often edge DaemonSets still "away"-parked | `kubectl get ds -A` with DESIRED 0; nodeSelector `away` | Patch out only the `away` key. |
| CNPG instance 0/1 after failover or shutdown | pg_rewind in progress, or idle-primary stall, or a true no-WAL-archive deadlock | `kubectl logs <inst> \| grep pg_rewind` (`% copied`, `Done!`, `could not restore file`) | Wait if it is progressing; idle stall → `select pg_switch_wal(); checkpoint;` on the primary; only a true deadlock → delete that instance's PVC. |
| Post-boot Error Jobs and high restart counts | Retries while Ceph or Postgres came up | Each has a Completed sibling | Ignore. |

## Investigation tools

- Prometheus: query through the API (NodePort from the workstation, ClusterIP from pods). `hubble_drop_total` has namespace labels.
- Per-guest Proxmox metrics are `proxmox_vm_*` (VMs and CTs). `proxmox_vm_cpu_percent` is a 0–1 fraction of the guest's vCPUs.
- Host access (SSH, sysfs writes, `helm install`, node exec) is often blocked for Claude. Hand the exact command to the user (`! <cmd>`) instead of working around the block.

## Reporting

State the matching row (or "new"), the check you ran and its output, and the proposed fix with who must run it. If the cause is new and non-obvious, offer to save it as a memory and add a row here.
