---
name: homelab-alert-triage
description: Triage a firing alert or odd symptom in the homelab (k0s production/edge clusters, Proxmox hosts, Ceph, CNPG, edge WAF, game probes) against the known causes and false alarms before digging. Use when an Alertmanager/Prometheus alert fires, a dashboard looks wrong, something "is down", backups silently stop, or the user asks "why is X alerting".
---

# Homelab alert triage

Most alerts here have a known cause, and several are known false alarms. **Match the symptom against the table before investigating**, then confirm with the listed check. Don't "fix" anything until the check confirms it. The user sometimes runs several agents at once, so an unexpected cluster change may be intentional. Ask before reverting it.

## Ground rules

- **DNS proves little.** `*.mgmt.wsh.no` is a wildcard, so every name under it resolves to the front-end. Confirm a host by IP plus a service answering on its port.
- **Test the path you claim.** On multi-homed hosts, binding a source IP doesn't choose the egress interface (use `SO_BINDTODEVICE` or `curl --interface <dev>`). Judge UDP reachability with something that round-trips (STUN/3478, NTP), never a one-way capture.
- **Freshly rebooted hosts look clean.** Some faults scale with uptime.
- Query Prometheus at 30-second steps for intermittent stalls. Five-minute steps average the spikes away.
- **Two rules can share one alert name.** Read the firing alert's labels and the rule's `expr` in `clusters/production/apps/observability/` before picking a row.
- Changes go through git. Live `kubectl` edits to Flux-owned fields get reverted on the next reconcile.

## Known causes and false alarms

| Symptom | Likely cause | Confirm with | Action |
|---|---|---|---|
| `KubeAggregatedAPIDown` for **several** APIs at once (metrics.k8s.io and kubescape), clears in ~5 min | A controller VM froze for a few minutes on an IO stall of its Proxmox host, its lease flapped, and k0s rolled the konnectivity agents | Without SSH: a 2–5 min gap in `up` for **one** apiserver instance; `proxmox_vm_pressureiofull_ratio` of that controller VM spiking (values are percent; baseline < 2); a new konnectivity-agent ControllerRevision created in the same minutes, differing only in the annotation `k0s.k0sproject.io/konnectivity-server-count-generation`. With SSH (user): etcd "heartbeat ... slow disk" in that controller's k0s log | Not netpol and not the apps. Find which controller and host it was this time (it has moved between controllers), then look at that host's storage. A Cilium restart also gives 2–4 minutes of this, so check the cilium pod ages. |
| `NodeDiskIOSaturation` **with a `device` label** (aqu-sq rule): huge aqu-sq and seconds of await, but util low | PVE kernel 7.0.14-x **bogus disk-time accounting** (32-bit ms wrap, a write charged since boot) | `rate(node_disk_io_time_weighted_seconds_total[5m]) * 300 / on(instance) group_left() (node_time_seconds - node_boot_time_seconds)` ≈ **1.11**; PSI io `full` near 0; `node_disk_io_now` 0 | Ignore. Not seen since the hosts moved to 7.0.14-14 and newer (ratio ≈ 0 on every host on 2026-11-17), so on a current kernel treat a firing as real until the ratio says otherwise. |
| `NodeDiskIOSaturation` **without a `device` label** (PSI rule, `node_pressure_io_stalled_seconds_total`) | A **real** IO stall; the bogus-accounting row does not apply | PSI io full > 0.3 on that host; the ratio query above gives ~0, not 1.11; which disks are busy and at what hour | Find the job. On the backup hosts a nightly run at the same hour is most likely a PBS garbage-collection or verify task on slow disks: confirm in the PBS task log (user), then accept it with a git-managed silence or threshold, or move the datastore. |
| Game external probes (`*UnreachableFromInternet`, `ExternalEndpointDown`, VPS `TargetDown`) | **Game server hibernated** (STS at 0/0) | `kubectl get sts -n <game>-production` | Expected noise. |
| Game external probes: **all** fail, scrape duration ≈ timeout | **Stale DDNS** after a WAN IP change | Compare the dynamic DDNS record (asked of its authoritative server) with the current egress IP | Ask the user who updates the record, fix it, then restart the probe exporters on the VPS. |
| Game probes **flap**, exporter logs "Unsupported protocol header", fails *faster* than success | **Duplicated UDP replies** on the office-pve-i9 path (r8169 offload) | tcpdump at the exporter shows two replies per query | `ethtool -K <nic> gro off gso off tso off tx off rx off` on the host, **then restart the exporters**, because they don't recover by themselves. |
| Cross-node pod networking broken on some nodes (DNS/TCP fail, ping works) | **Realtek r8169 VXLAN checksum offload** on office-pve-i9 | Which PVE host the node runs on (`qm list`) | Disable offloads on the uplink and persist them. Don't chase Cilium, MTU or identity. |
| `*-pbs-backup` pods Pending; backups silently stop | Node short on CPU or memory **requests** (common after reboots), or a big-request squatter on the 2-core node | `kubectl describe node <n>` Allocated resources; `kubectl get jobs -A \| grep -v Complete` | Move Deployment pods off the node (see k0s-node-maintenance rebalance). **Never change the backup affinity.** |
| `KubeJobFailed` `DeadlineExceeded` on a `*-pbs-backup` Job that normally takes seconds | The app's node has a taint the backup does not tolerate (k0s-prod05: `wsh.no/dedicated=truenas-colocated:PreferNoSchedule`). The taint outweighs the preferred pod affinity, so the backup lands on another node and the app's RWO PVC cannot attach there | `kube_pod_status_phase` for the backup pod: `Pending` for the whole deadline, bound (`kube_pod_info`) to a different node than the app | Give the backup CronJob the same toleration as its app (all backups should tolerate every taint their app may run on). Delete the failed Jobs to clear the alert. |
| Edge SDR pod `CreateContainerError` "lstat /dev/bus/usb/00X/00Y: no such file", or new pods `UnexpectedAdmissionError` "requested device does not exist" | The RTL-SDR dongles re-enumerated after a USB reset. A pod keeps the device path it was allocated, and `generic-device-plugin` keeps a stale device list | Node allocatable `sdr.wsh.no/rtlsdr-*` shows 0 for a dongle that is plugged in; pod events | Delete the `generic-device-plugin` pod on that Pi first, check allocatable is back to 1, then delete each stuck SDR pod (user's yes per delete). No replug needed. |
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

- Prometheus: query through the API (NodePort from the workstation, ClusterIP from pods). Find the port with `kubectl get svc -n observability-production | grep prometheus` and use any node IP from `kubectl get nodes -o wide`. `/api/v1/alerts` lists what fires now; `ALERTS{alertstate="firing"}` over a range gives history.
- Retention is 15 days (or 18 GB). Longer ranges are cut without an error.
- `hubble_drop_total` has namespace labels.
- Per-guest Proxmox metrics are `proxmox_vm_*` (VMs and CTs). `proxmox_vm_cpu_percent` is a 0–1 fraction of the guest's vCPUs, while `proxmox_vm_pressure*_ratio` holds percent values. `proxmox_vm_*` also tells you which host a node VM runs on; that moves, so don't trust an older note.
- Host access (SSH, sysfs writes, `helm install`, node exec) is often blocked for Claude. Hand the exact command to the user (`! <cmd>`) instead of working around the block.

## Reporting

State the matching row (or "new"), the check you ran and its output, and the proposed fix with who must run it. If the cause is new and non-obvious, offer to save it as a memory and add a row here.
