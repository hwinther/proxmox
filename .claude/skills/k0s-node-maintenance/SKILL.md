---
name: k0s-node-maintenance
description: Procedures for k0s cluster node work, covering host or node reboots, rebalancing pods afterwards, k0s Autopilot version upgrades, drains with CNPG/RabbitMQ/ceph-rbd, node VM changes (CPU type, migration between Proxmox hosts), k0s-managed charts and node sysctl/kernel issues. Use when planning or doing a reboot, upgrade, drain, VM move or node fix on the production or edge-sdr k0s clusters, or after one when the cluster looks unbalanced.
---

# k0s node maintenance

**Production:**
- controllers prod01–03, workers prod04–05;
- Alpine, OpenRC (`k0scontroller`/`k0sworker`), logs in `/var/log/k0s.log`.

**edge-sdr:**
- controller edge01, plus the arm64 Pis radio-pi01 and radio-pi02 (Debian trixie).

The versioned controller config is `infra/k0s/production/k0s.yaml`. Runbooks:
- `infra/k0s/autopilot/README.md`
- `infra/k0s/return-from-shutdown.md`
- `infra/k0s/away-mode.md`
- `infra/k0s/node-onboarding.md`

**Read the relevant runbook first** and correct it when reality differs.

Host-side commands (SSH, sysfs, sysctl, `helm install`, `qm`) are usually blocked for Claude. Prepare the exact commands and let the user run them.

## Node sizes (allocatable)

| node | cores | role |
|---|---|---|
| prod01 | 8 | largest; absorbs load |
| prod02 | 2 | keep light |
| prod03 | 6 | `node.wsh.no/gameserver=true` |
| prod04 | 6 (low memory) | gameserver label |
| prod05 | 2 | `topology.wsh.no/colocated-with=truenas`; NAS-adjacent workloads prefer it |

The two 2-core nodes should not run much. The game servers on prod03/04 and the NAS-colocated stack on prod05 are intentional.

## Before any reboot, drain or upgrade

1. Check what moves: `kubectl describe nodes | grep -A5 'Allocated resources'`. If the remaining nodes can't fit the drained node's requests, the drain hangs or pods pend.
2. **CNPG:** primaries have PDBs (minAvailable 1).
   - Cordon the node early and CNPG usually switches over by itself.
   - If not, set `targetPrimary` via the status subresource.
   - Make sure the replica is **not** on the next node to be drained.
3. **RabbitMQ:** it has a PDB with maxUnavailable 1, but no anti-affinity, so members can share a node.
4. **Hibernated games:** expect no backups; that's fine.
5. **Shutdown of everything:** `flux suspend kustomization postgres-cnpg-production` **before** annotating CNPG hibernation, because Flux strips the annotation. Follow `return-from-shutdown.md`.
6. Take a k0s backup on the leader before an upgrade.

## Autopilot upgrades (k0s version)

- Plans are committed under `infra/k0s/autopilot/` (Flux doesn't watch that path) and applied by hand. Each is a one-shot singleton named `autopilot`.
- Verify the binary sha256 against the release `sha256sums.txt`. Do edge-sdr first as the trial, then production.
- Autopilot **drains every node** and **doesn't follow the list order**. Prepare **all** nodes before applying, for example the containerd v3-format drop-ins on the Pis for k0s ≥ 1.36.
- `kubectl get controlnodes` should list exactly the live controllers. A stale entry makes the Plan wait forever.
- The kubeconfig server (prod01) disappears while prod01 restarts. Use `--server https://<another controller>:6443` in watch loops.
- Expected noise during and after the upgrade:
  - Ready=Unknown for about a minute per node;
  - konnectivity re-pulling images on the Pis;
  - the kyverno-policies dry-run failing until admission is back;
  - Error pods left from evictions.
- After the upgrade:
  - check for **stale rbd mappings**: RWO pods stuck "still being used" (fix in homelab-alert-triage);
  - **rebalance** (below);
  - check that Flux supports the new Kubernetes minor version, and the reverse.

## Rebalance after reboots (always do it)

Kubernetes never moves running pods, so the last node back stays empty while others hit 90%+ requests. The backup pods, pinned to their app's node, then pend and backups stop silently.

1. Find nodes over about 90% CPU or memory requests.
2. Move **Deployment** pods: `kubectl rollout restart` (surge, no downtime). Delete StatefulSet pods only where a brief restart is fine.
3. To steer placement, cordon the full nodes around the restart, then uncordon. Default scoring sends pods to the emptiest node.
4. If prod05 came back empty, delete the NAS-colocated pods so they return to it by preference.
5. **Never move CNPG instance pods** for balancing. For RabbitMQ, move the operator, not the members.
6. Watch memory when moving game pods: their affinity is only preferred, and large ones overload prod04.
7. Afterwards, Pending backup Jobs schedule by themselves. Check with `kubectl get jobs -A | grep -v Complete`.

## Node VM changes (Proxmox)

- **CPU type:** every k0s node needs AVX2 (`x86-64-v3` or `host`), because ceph-csi ≥ 3.18 and RHEL10-based images fail with "CPU does not support x86-64-v3". The change needs a stop and start.
- Never give a VM all of the host's threads, and use 1 socket × N cores.
- **Migrating a VM with a local ZFS disk** is offline, and the target needs the same storage ID.
  - A thick zvol on a nearly full pool fails the snapshot. Set `refreservation=none` on the source, then `auto` on the target.
  - Start the migration from the PVE task or API, not an SSH session that may drop.
- Avoid Realtek r8169 NICs for node hosts (VXLAN offload bug). If one must be used, disable offloads and persist that.

## k0s-managed charts and extensions

- **Removing a chart from k0s.yaml runs helm uninstall, even with the finalizer stripped.** That took production's CNI down once.
- Cilium is now a Flux HelmRelease. For any other k0s-managed chart, plan removal as a short outage: have the exact version and a backup of the values ready for an immediate `helm install`, run by the user.
- Editing controller k0s config: edit all controllers, restart the followers first, then the **leader**. The leader is the holder of `kube-node-lease/k0s-endpoint-reconciler`.

## Node OS issues

- `apk upgrade` replaces the running kernel's modules, so modules that weren't loaded (nfsv4) can't load until reboot. Reboot after kernel upgrades.
- inotify limits: nodes provisioned before the cloud-init fix need `/etc/sysctl.d/90-inotify.conf` (8192 / 524288).
- After host reboots, check Proxmox-side units such as `zfs-volume-wait`.
- Edge "away" parking sets `nodeSelector away=true` on edge DaemonSets and Deployments. **Flux does not remove it.** Patch out only that key, and check `get ds -A` for DESIRED 0.

## Finish

Report what was done per node and confirm each of these:
- all nodes Ready and uncordoned;
- Kustomizations and HelmReleases Ready;
- no Pending or ContainerCreating pods with RWO PVCs;
- CNPG clusters healthy (`kubectl get clusters.postgresql.cnpg.io -A`);
- request balance roughly even;
- backup Jobs completing.
