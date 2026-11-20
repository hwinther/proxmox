# Cluster backlog

Open work for the homelab clusters, checked against the live state on **2026-11-16**. Each item says what is true today, what to do, who must do it and when it counts as done. Items marked **host** need commands on a Proxmox host, which the owner runs.

Bigger pieces have their own plan under [`plans/`](plans/). Finished plans are not kept here; their history is in the merged PRs.

Edge/WAF items and game-server alert items live in the private-apps repo (`infra/backlog.md`), because they describe topology that stays out of this public repo.

When you finish or re-check an item, update it here in the same PR.

## Decide soon

### 1. Kyverno 1.20 (PR #1045)

- **State:** Renovate PR #1045 bumps the chart 3.9.2 → 3.10.0 (Kyverno 1.19.2 → 1.20.0, released 2026-11-12) on both clusters at once. No legacy `kyverno.io/v1` or `v2` objects remain in either cluster or in git, so the migration that blocked this is finished. The chart's new pre-upgrade hook `check-legacy-policies` should pass.
- **Do:** the owner decides when to merge. Merge when someone can watch: the hook Job, the four controllers, then `flux reconcile kustomization kyverno-policies`. Check afterwards that PolicyReports still show the PolicyExceptions as `skip`.
- **Related, not verified here:** upstream issue kyverno/kyverno#18671 (reported for 1.19.2 and 1.20.0) says a GeneratingPolicy clone can inherit the source Secret's `ownerReferences` and get garbage-collected when the source is updated. Check which clone sources carry owner references: `kubectl get secret -A -o json` filtered to the source Secrets named in `bases/kyverno-platform/` and `clusters/*/apps/kyverno-policies/`. CNPG-owned credential Secrets are the likely case.
- **Done when:** #1045 is merged or closed with a reason, and the owner-reference question has an answer written here.

### 2. Dependency review: does workload identity work on Dependabot PRs?

- **State:** `.github/workflows/dependency-review.yml` authenticates with workload identity federation; the `ANTHROPIC_API_KEY` secrets are deleted. Verified 2026-11-20 on three Renovate PRs, all green with a review comment: #1048 loki patch $0.10 (11 turns), #1045 kyverno minor $0.15 (16 turns), #970 kube-prometheus-stack major $0.15 (12 turns). Still open: GitHub treats Dependabot-triggered runs like fork runs, and the docs don't say whether they get an OIDC token.
- **Do:** when the next Dependabot PR under `clusters/` or `bases/` opens, check its `review` run. If the token request fails, either skip the job for `dependabot[bot]` or accept that those PRs get no review.
- **Done when:** one Dependabot run has shown whether OIDC works, and the workflow handles the answer.

## Node and host placement

### 3. Two k0s nodes share one host

- **State:** `k0s-prod03` and `k0s-prod04` both run on office-pve-i9, which also carries one of three etcd members, one of three Ceph OSDs and a mon. Rebooting that host drains two nodes at once and leaves etcd and Ceph without margin. All three CNPG primaries were on prod03 on 2026-11-16. That host also has the Realtek r8169 NIC; the offload fix there is permanent (owner, 2026-11-17).
- **Do (host):** move `k0s-prod04` to shuttle03 as planned on 2026-11-07. The VM disk is a local ZFS zvol, so it is an offline migration: follow "Node VM changes" in the `k0s-node-maintenance` skill. Reduce it to 4 vCPU, because the target has 4 threads. Before that, drain the node and rebalance afterwards.
- **Done when:** `proxmox_vm_*` shows prod03 and prod04 on different hosts.

### 4. shuttle03 is not monitored as a host

- **State:** the scrape targets (`10.20.4.36:9100` in `node-exporter-pve`, `10.20.4.36:9633` in `smartctl`) and the row in `clusters/production/apps/observability/host-exporters.md` are in git. The exporters are not installed on the host yet, so both targets are down until they are. Proxmox's own OTLP metrics (`proxmox_node_*`, `proxmox_vm_*` with `node="shuttle03"`) already arrive.
- **Do (owner, on the host):** install node-exporter, lm-sensors and smartctl_exporter as `host-exporters.md` describes, and allow 10.20.13.0/24 to tcp/9100 and tcp/9633 if the host firewall is on.
- **Done when:** `up{job="node-exporter", instance="shuttle03"}` is 1 (the host scrape is relabelled to that job name) and `NodeCpuOverheating` covers it.

### 5. Controller freezes behind `KubeAggregatedAPIDown`

- **State:** four times between 2026-11-10 and 2026-11-16 the host office-pve-amd had an IO stall of 3–4 minutes, the `k0s-prod01` VM froze, and the aggregated APIs were unavailable for a few minutes. Evidence is in Prometheus only (host PSI io, `proxmox_vm_pressureiofull_ratio`, apiserver scrape gaps). The cause on the host is unknown.
- **Do (host):** during or right after the next episode, collect `zpool iostat -w`, `zpool status`, the trim and scrub schedule and `dmesg` for the NVMe on office-pve-amd, and the etcd "slow disk" lines in `/var/log/k0s.log` on prod01.
- **Done when:** the cause is named in the `homelab-alert-triage` skill row, with a fix or a decision to accept it.

### 6. Nightly IO alert on the backup host

- **State:** the PSI-based `NodeDiskIOSaturation` fires on pbs-ks every night from about 23:20 UTC for 15–120 minutes. It is a real stall on the two slow datastore disks, most likely PBS garbage collection or verify. The job is not confirmed.
- **Do:** the owner checks the PBS task log for that hour. Then either add a threshold or time-window exception for that host in `prometheusrule-node-disk.yaml`, or move the datastore to faster disks.
- **Done when:** the alert no longer fires nightly, or the rule documents why it may.

### 7. shuttle01 CPU swap (optional)

- **State:** shuttle01 has a CPU without AVX2. It no longer hosts a k0s node, so nothing in the cluster waits for this. The host runs the router and DHCP, so the swap is an on-site outage.
- **Do (owner):** swap in the spare AVX2 CPU when convenient. Until then, don't migrate VMs with CPU type `host` or `x86-64-v3` to shuttle01.
- **Done when:** swapped, or dropped from this list.

### 7a. prod05 runs an older kernel than the other nodes

- **State:** on 2026-11-17 `k0s-prod05` runs 6.18.48 and the other four run 6.18.58. If `apk upgrade` has already run on prod05 without a reboot, modules that were not loaded (nfsv4) cannot load, and this is the node that mounts the NAS.
- **Do (host):** compare `uname -r` with `ls /lib/modules` on prod05. If they differ, plan a reboot with the `k0s-node-maintenance` skill.
- **Done when:** all five nodes report the same kernel.

## Scheduling

### 8. The 2-core NAS-adjacent node is nearly full

- **State:** CPU requests on 2026-11-16: prod05 75 %, prod03 56 %, prod04 46 %, prod02 43 %, prod01 40 %. Memory requests: prod04 76 %, prod05 70 %. One extra pod with a large request on prod05 blocks the nightly backup pods, which are pinned to their app's node.
- **Do:** find pods on prod05 that have no reason to be there (no NAS mount, no `topology.wsh.no/colocated-with` preference) and give them a node affinity away from it, in git. Don't change the backup affinity.
- **Taint applied 2026-11-17:** the soft `PreferNoSchedule` taint (`wsh.no/dedicated=truenas-colocated`) is on the node now. It is set by hand, not from git, and it evicts nothing.
- **Found the same day:** the NAS-adjacent apps that tolerate the taint all run on prod01, with their NFS mounts working, so they no longer depend on this node. prod05 holds generic pods instead (a RabbitMQ member, a few Deployments, a game server).
- **Open decision (owner):** either bring the design back (move the generic Deployment pods off with `kubectl rollout restart`, then restart the NAS-adjacent apps so their preferred affinity returns them here; never move the RabbitMQ member by deleting it without checking the other two are healthy), or drop the colocation (remove the taint, the tolerations and the README section in private-apps).
- **Done when:** prod05 stays under about 60 % CPU requests after a reboot-and-rebalance cycle.

### 9. Containers without a memory request

- **State:** 69 running containers have no memory request: 29 in `ceph-csi-production`, 25 in `kube-system`, 15 in `observability-production`. The scheduler undercounts those nodes.
- **Do:** set requests in the HelmRelease values of ceph-csi and the observability charts (use the last week's `container_memory_working_set_bytes` p95). `kube-system` is mostly Cilium and k0s components: set Cilium's in `clusters/production/apps/cilium/helmrelease.yaml`, leave k0s-managed pods.
- **Done when:** the count is below 30 and the rest are k0s-managed.

## Networking

### 10. Cilium netkit datapath trial

- **State:** Cilium 1.20.4 runs as a Flux HelmRelease. The config-drift alert is in place. `bpf.datapathMode` is still the default (veth). All nodes run kernel 6.18.
- **Do:** first confirm in the Cilium docs for the running version that netkit works with `routingMode: tunnel` (VXLAN) and with the egress gateway. Then set `bpf.datapathMode: auto` in a PR and roll it in a quiet window; pods must be recreated to switch. Verify with the checklist in `infra/k0s/cilium-k0s-setup.md` plus egress SNAT.
- **Done when:** tried and kept, or tried and reverted with the reason noted here.

### 11. Cluster-wide baseline policy (later)

- **State:** every namespace carries three copies of the netpol baseline. Kubernetes `ClusterNetworkPolicy` (Baseline tier) could replace them with one object, but the API is alpha.
- **Do:** nothing until the API is beta. Then note that a Baseline tier also applies to `kube-system` unless excluded.

### 10a. Standing policy drops seen by Hubble

- **State (2026-11-16):** `hubble_drop_total{reason="POLICY_DENIED"}` shows a steady drop from kubescape to a non-pod destination (about 0.9 per second, since June) and a small one into one of the private-apps namespaces.
- **Do:** identify each flow with `hubble observe --verdict DROPPED -n <namespace>`, then allow it or note here why the drop is wanted.
- **Done when:** both are allowed or documented.

## Policy and supply chain

### 12. Re-survey policy report noise

- **State:** the 2026-10-03 survey listed noisy results, but all policies have since moved to the CEL policy types, and the trusted-sources policy already accepts the SSH-over-443 URL. The old list is not valid any more.
- **Do:** list failing PolicyReport results per policy (`kubectl get policyreport -A -o json`), group them, and fix or except the top three sources. System DaemonSets (Cilium, ceph-csi, node-exporter) are expected to fail the pod-security style checks.
- **Done when:** a short current list is written here.

### 13. Audit-mode signature policy for third-party images

- **State:** first-party images are verified at admission. A spot check of 47 third-party images on 2026-10-27 found keyless cosign signatures or attestations on Cilium, the Flux controllers, cert-manager, trust-manager, prometheus-operator, otel-collector-contrib, the CNPG operator and its postgresql image, Kyverno, policy-reporter, kubescape and headlamp. The observability stack, ceph-csi, the k0s images, Authelia and most community images had none.
- **Do:** add one `ImageValidatingPolicy` in **Audit** for the signed set, each entry pinned to the vendor's signer identity (for example the vendor's release workflow on `refs/tags/v*`). Never Deny on cluster-critical images (CNI, admission controller, Flux, DNS, CSI): a failed verification would block the cluster's own recovery. Re-check the list with `cosign verify` before writing it; it is three weeks old. For the unsigned majority the controls stay digest pinning and in-cluster scanning.
- **Done when:** the policy reports results for the signed set and nothing is blocked.

### 13a. Digest pins in git for our own images

- **Decision (owner, 2026-11-17):** our own images are pinned by digest in git and verified for signature and attestations; third-party images get an exception only with a good reason.
- **State:** one first-party image and 13 third-party image lines carry `tag@sha256` today. The rest of the first-party images are tag-only, and the admission policy runs with `verifyDigest: false` and adds the digest itself. App manifests that come from OCI artifacts are rendered in the app repos, so the pin has to be produced there.
- **Do:** first write down how the pin is produced and kept current: the release workflow that renders the manifests artifact writes `tag@sha256`, and Renovate or Dependabot must move tag and digest together. Then convert one app end to end, check that the policy still admits it with `verifyDigest: true` for that image, and roll out. List the third-party images that stay unpinned or unverified, each with its reason.
- **Done when:** every first-party image reference in git has a digest, and the exceptions list exists.

### 13b. Leftovers after removing mqttui (owner)

- **State:** the mqttui web inspector was removed from `mosquitto-production` on 2026-11-20 (unmaintained since 2026-03; its image carried 155 critical CVEs). Flux prunes the Deployment, route and policies. Two things Flux does not own stay behind.
- **Do (owner):** delete the `mqttui-mqtt` Secret in `mosquitto-production`, and remove the `mqttui` user from the broker password file by regenerating the `mosquitto-auth` Secret without it (see `mosquitto-secrets.md`). Drop the `mqtt.mgmt.wsh.no` entry from the mgmt front-end if it has one.
- **Done when:** no `mqttui` user or Secret is left.

### 14. Promotion and rollback of the pinned production app, untested paths

- **State (as of 2026-10-29, not re-checked):** the approval-gated `promote.yml` flow had only been run in sign-only mode. A real forward promotion PR and a rollback had not been exercised.
- **Do:** check the app repo's `promote.yml` run history. If a forward promotion and a rollback have both run since, remove this item.

## Data

### 15. Postgres continuous archiving (on hold)

- **State:** CNPG `spec.backup` is empty on all clusters. Data is covered by PBS dump jobs; there is no point-in-time recovery, and a standby can wedge in `pg_rewind` after an unplanned failover.
- **Do:** nothing unless the owner asks. It needs object storage first (Ceph RGW was deferred).
- **Note:** a CNPG chart bump restarts every instance, the primary in place, so expect a few minutes without the database.

## Parked by the owner

Don't start these without being asked.

- **SDR hardware variants beyond RTL-SDR:** wait until there is a real device to test. The approach is per-variant image tags from one Dockerfile plus a device-plugin entry.
- **Native arm64 runners for image builds:** build time is not a problem today.
- **Ceph cephx step 2:** see [`plans/ceph-cephx-aes256k-step2.md`](plans/ceph-cephx-aes256k-step2.md); waits for kernel 7.0 on every node.

## Plans

| Plan | State |
|---|---|
| [Secrets: OpenBao + External Secrets](plans/openbao-eso.md) | Next platform item. Three decisions needed before any work. |
| [Ceph cephx aes256k, step 2](plans/ceph-cephx-aes256k-step2.md) | Parked until every node runs kernel 7.0 (earliest about 2027-05). |
