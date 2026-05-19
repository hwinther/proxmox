# Cilium / k0s incident — summary & remaining process

Status date: 2026-05-17. Handover doc (not committed). Authoritative detail:
`TMP-cilium-incident-remediation-plan.md`. Gate tool: `scripts/k0s-reconverge-check.sh`.

---

> ## ⚠️ CORRECTION — VERIFIED ROOT CAUSE (2026-05-17, supersedes the prod04 section)
>
> The "prod04 **node-intrinsic** datapath fault" was a **misdiagnosis**. Real cause:
> the Proxmox host **office-pve-i9** has a **Realtek `r8169`** NIC with the VXLAN/UDP
> tunnel checksum-offload bug — it blackholes **VXLAN-encapsulated TCP/UDP** while
> **ICMP + native node traffic (etcd/SSH/kubectl) work**. Both broken nodes (prod04,
> and prod03 once migrated there) are on office-pve-i9; the healthy nodes
> (prod01/02/05) are on Intel-NIC hosts. The count-based tcpdump "wire is clean / not
> office-pve-i9" conclusion was invalid (corrupted packets are on the wire but dropped
> at the receiver on bad checksum). **Fix (verified):** `ethtool -K enge0 gro off gso
> off tso off tx off rx off` on office-pve-i9, persisted in `/etc/network/interfaces`
> → prod03 cluster-health 2/5→5/5, all cross-node traffic restored. prod04 now only
> needs node-delete + cloud-init rebuild **as a worker** (will succeed now). Memory:
> `office-pve-i9-r8169-vxlan-fault`.

## TL;DR

- **Resolved.** Cluster is healthy and serving on **prod01 / prod02 / prod05**,
  Cilium **v1.19.4**, gate GO, etcd quorum intact.
- **prod04** remains **cordoned / drained / empty**. ~~node-intrinsic datapath
  fault~~ → **actually office-pve-i9's r8169 NIC** (see CORRECTION box). It is now
  cleanly removed from etcd (cluster = prod01/02/03). Remaining: `kubectl delete node
  k0s-prod04` + CiliumNode cleanup, then rebuild **as a worker**. No urgency.

---

## Root cause (what actually broke)

A rolling Proxmox patch-reboot of control-plane nodes dropped etcd below quorum,
which cascaded:

1. etcd quorum loss → kube-apiserver flapping → **cilium-operator crash-looped** for
   ~a day (couldn't hold its lease) → corrupted/inconsistent Cilium security
   identities → cross-node pod traffic dropped ("Policy denied").
2. A **43-day-old stuck Helm release** (`sh.helm.release.v1.cilium.v13` =
   `pending-upgrade`) silently blocked every k0s Cilium upgrade.
3. Latent config problem exposed by agent restarts: live Cilium
   `k8sServicePort: 6443` (drifted from the repo's `7443`). `6443` only works on
   control-plane nodes (local apiserver); the **worker prod05** has no local
   apiserver → its agent crash-looped. The intended endpoint is k0s **NLLB**
   (node-local LB) on `127.0.0.1:7443`, present on every node.
4. NLLB itself was inconsistent: prod01/prod02 (hand-built from Alpine ISO) had a
   non-standard `/etc/hosts` where `localhost` → `::1`, so k0s NLLB envoy bound
   **IPv6-only `[::1]:7443`**; prod04/prod05 (cloud-init) correctly bound
   **`127.0.0.1:7443`**. Cilium uses IPv4 → only reached NLLB on the cloud-init nodes.
5. **prod04**: a separate, node-intrinsic datapath fault (independent of all the
   above) that survived every software/state remedy.

---

## The fix that was applied (Phase A — DONE, successful)

1. **Cleared the stuck Helm release** so k0s could upgrade Cilium:
   `kubectl -n kube-system delete secret sh.helm.release.v1.cilium.v13`
   (backup: `O:\proxmox\TMP-cilium-helm-v13-pending-backup.yaml`). Last *deployed*
   was v12; v13 was a never-completed `pending-upgrade`.
2. **Upgraded Cilium 1.19.2 → 1.19.4** (k0s helm extension): bumped
   `version: "1.19.4"` in live `/etc/k0s/k0s.yaml` on all 3 controllers; gated
   `rc-service k0scontroller restart` one-at-a-time until the k0s **leader**
   (prod01) re-read config and k0s helm-upgraded. (Repo IaC already bumped:
   `infra/k0s/k0s.yaml.example`, `infra/k0s/cilium-k0s-setup.md` — uncommitted.)
3. **Normalized `/etc/hosts` on prod01 & prod02** so `getent hosts localhost`
   → `127.0.0.1` (backups: `/etc/hosts.bak.pre-nllb-fix` on each node). End state:
   ```
   127.0.0.1 <fqdn> <shorthost> localhost.localdomain localhost
   ::1       localhost6.localdomain6 localhost6
   ```
4. **Regenerated NLLB** on prod01/02 via gated k0scontroller restarts → envoy now
   binds `127.0.0.1:7443` on **all 4 nodes** (verified via `/proc/net/tcp` —
   tooling-independent; `ss`/`nc` give false negatives on these Alpine nodes).
5. **Flipped Cilium `k8sServicePort: 6443 → 7443`** in live `/etc/k0s/k0s.yaml` on
   all 3 controllers (backup `.bak.pre-7443`; now matches the repo intent), gated
   leader restart → k0s reconciled the Chart → Cilium DS rolled → **prod05
   recovered**, all 4 agents Ready, gate GO.

Result: original outage resolved; prod05 back; config drift corrected; on 1.19.4.

---

## Current cluster state

| Node | Role | State |
|---|---|---|
| prod01 (10.20.13.11) | control-plane | healthy, serving, Cilium 1.19.4 |
| prod02 (10.20.13.12) | control-plane | healthy, serving (uncordoned + control-plane taint removed earlier for capacity) |
| prod04 (10.20.13.14) | control-plane | **cordoned/drained/empty — node-intrinsic Cilium datapath fault; awaiting B3** |
| prod05 (10.20.13.15) | worker | healthy, recovered by Phase A |

etcd: 3 members (prod01/02/04) — quorum healthy. prod04's etcd is still a member;
B3 must cleanly remove it (see below).

~~Why prod04 is B3~~ [RETRACTED — see CORRECTION box]: the fault survived 1.19.4,
operator fix, agent rolls, reboots, Phase A, state wipe **because none of those touch
the hypervisor NIC**. The count-based tcpdump "wire is clean, not office-pve-i9"
inference was the error — corrupted r8169 packets transit the wire (counts match) but
the receiver drops them on bad checksum. It is intrinsic to the **host
office-pve-i9**, not the node. Fix = the host `ethtool -K enge0 ...` change (done,
verified), **not** a prod04 rebuild.

---

## Remaining process

### B3 — re-provision prod04 (planned window; no urgency, zero impact)

Pre-reqs: `scripts/k0s-reconverge-check.sh` → **GO**; prod01 & prod02 etcd healthy
(prod04 leaving = 2/3 quorum, fine). Do this as a deliberate, gated operation — it
is an **etcd-membership change**.

1. Confirm prod04 is still cordoned & empty (`kubectl get node k0s-prod04`,
   `kubectl get pods -A -o wide | grep k0s-prod04` → only daemonset/system).
2. Remove prod04 from etcd cleanly — on prod04:
   `k0s etcd leave --peer-address https://10.20.13.14:2380`
   (verify with `k0s etcd member-list` from a healthy controller → prod04 gone).
3. `kubectl delete node k0s-prod04`; `kubectl delete ciliumnode k0s-prod04
   --ignore-not-found`.
4. Re-provision the prod04 VM from the **cloud-init** template (same path that built
   prod05 — gives correct `/etc/hosts`, clean k0s, fresh identity). See
   `infra/cloud-init/` + `infra/k0s/node-onboarding.md`.
5. Re-join as a controller; verify: etcd member re-added (`k0s etcd member-list`),
   gate **GO**, prod04 `cilium-dbg status` → **Cluster health 4/4**, a prod04-pinned
   test pod resolves DNS + reaches a Service + cross-node pod (use the
   `netprobe` busybox pattern, nodeName k0s-prod04).
6. It comes up fresh/uncordoned — done. Cluster back to 4 nodes.

Rollback / safety: if anything is off, leave prod04 out — the cluster is fine on 3
nodes. Never take a 2nd control-plane node down concurrently; gate **GO** between
every controller restart.

### Phase C — cleanup (anytime)

- [ ] Commit the IaC bumps: `infra/k0s/k0s.yaml.example` + `infra/k0s/cilium-k0s-setup.md`
      (Cilium 1.19.4). These are already edited, uncommitted.
- [ ] Re-sync any remaining drift between live `/etc/k0s/k0s.yaml` (all controllers)
      and `infra/k0s/k0s.yaml.example` (the key `k8sServicePort` now both `7443`;
      diff the rest — hubble.ui, cluster.name, tolerations).
- [ ] Decide capacity posture (prod02's control-plane taint was removed for capacity
      during the incident — re-add if desired once prod04 is back).
- [ ] Delete the `TMP-*.md` handover files and `TMP-cilium-helm-v13-pending-backup.yaml`
      once prod04 is reprovisioned and everything is committed.
- [ ] Optionally reprovision prod01/prod02 via cloud-init eventually so all nodes are
      identical (their `/etc/hosts` is now patched in place; this is the durable parity).

---

## Hard rules / lessons (carry forward)

- **One control-plane node down at a time**; run `scripts/k0s-reconverge-check.sh`
  to **GO** between every restart/reboot. Losing etcd quorum (2 of 3) is what
  triggered this entire incident.
- **Pre-flight any cluster-wide Cilium endpoint change**: confirm
  `127.0.0.1:<port>` LISTEN on **all** nodes via `/proc/net/tcp` (hex `:1D13`=7443,
  `:192B`=6443, state `0A`) before flipping. A naive flip nearly caused a full
  outage; this check prevented it.
- **k0s helm extensions have no GitOps reconcile**: a stuck `pending-upgrade` Helm
  release silently blocked upgrades for 43 days. Periodically check
  `kubectl -n kube-system get charts.helm.k0sproject.io` and the
  `sh.helm.release.v1.cilium.*` secret statuses.
- **k0s static config drift is invisible**: live `/etc/k0s/k0s.yaml` had drifted
  from `infra/k0s/k0s.yaml.example`. Periodically diff live ↔ repo.
- **Tooling on the Alpine nodes is unreliable** (`ss`, `nc -z`, `/dev/tcp`,
  `crictl` gave false negatives). Use `/proc/net/tcp{,6}` and `envoy.yaml` /
  `cilium-dbg` for authoritative answers.
- Cilium 1.19.4 carries the upstream fixes matching this incident: operator
  identitygc nil-deref on shutdown (#45091), ipcache identity update hang (#44597),
  datapath reinit stuck via local API (#45557), agent retry-instead-of-Fatal on
  transient errors (#44526).
