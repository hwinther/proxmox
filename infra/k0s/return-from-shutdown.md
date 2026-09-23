# Return from a full shutdown

Reverse of the extended-absence shutdown (see [away-mode.md](away-mode.md) for the SDR side).
Written 2026-09-01 during the actual shutdown. **Order matters** — each step depends on the one
before it.

## 1. Proxmox + Ceph

1. Power on all Proxmox hosts. Wait for Ceph to form quorum and settle before touching anything.
2. Clear the maintenance flags set during shutdown:

   ```bash
   ceph osd unset noout
   ceph osd unset norebalance
   ceph osd unset nobackfill
   ceph osd unset norecover
   ceph -s          # wait for HEALTH_OK before starting VMs
   ```

   Starting VMs while Ceph is still recovering means every RBD read competes with backfill on a
   three-OSD consumer-SSD tier. Wait.

## 2. Production cluster

3. Start the k0s VMs (controllers first, then workers). Confirm all nodes `Ready`.
4. **Un-hibernate the CNPG clusters.** They were hibernated so that Postgres shut down cleanly —
   none of them archive WAL, so an unclean stop risks a `pg_rewind` deadlock
   (see the `cnpg-no-wal-archive-rewind-deadlock` note).

   ```bash
   K="kubectl --context Production"
   $K -n postgres-production annotate cluster postgres-prod cnpg.io/hibernation=off --overwrite
   $K -n postgres-test       annotate cluster cluttertestdb cnpg.io/hibernation=off --overwrite
   $K -n postgres-test       annotate cluster testdb        cnpg.io/hibernation=off --overwrite
   $K get pods -A -l cnpg.io/podRole=instance -o wide      # expect 6 pods, 2 per cluster
   ```

   State at hibernation (2026-09-01): all three healthy, 2 instances each, primary on the `-1`
   pod, all 6 PVCs (5Gi) retained `Bound`. Nothing needs re-cloning.

   **What actually happened on 2026-09-22.** The hibernation did not hold — see
   [Before the next shutdown](#before-the-next-shutdown). All three clusters had been running at
   power-off, so every `-1` instance came back with `Database cluster state: in production` and the
   operator ran `pg_rewind` against the surviving `-2` primary. All three rewinds succeeded; no data
   was lost and nothing needed re-cloning. Budget a few minutes for the 600-750 MB copy per cluster.

   **If an instance sits at `0/1 Running` after the rewind finishes**, check for an idle-primary
   stall before assuming anything is broken:

   ```bash
   K="kubectl --context Production -n <ns>"
   $K logs <cluster>-1 | grep -E 'pg_rewind: Done|Minimum recovery ending location'
   $K exec <cluster>-2 -c postgres -- psql -U postgres -tAc "select pg_current_wal_lsn();"
   ```

   `pg_rewind` writes a `minRecoveryPoint` a few bytes past the primary's current insert LSN (it
   includes the next WAL page header). A completely idle primary never writes those bytes, so the
   standby streams, catches up, and still refuses connections with
   `Consistent recovery state has not been yet reached` — forever. Replication is healthy; there is
   simply no WAL to send. Any write on the primary unblocks it:

   ```bash
   $K exec <cluster>-2 -c postgres -- psql -U postgres -tAc "select pg_switch_wal(); checkpoint;"
   ```

   On 2026-09-22 `testdb-1` needed exactly this: standby wanted `0/5B000028`, primary was parked at
   `0/5B000000`. Forty bytes. It became ready within seconds of the switch.

5. Expect post-reboot pod imbalance — k8s never rebalances on its own. See the
   `k0s-post-reboot-rebalance-recipe` note, and check `pbs-backup` CronJobs actually ran.

## 3. Edge-SDR cluster

6. Power on `k0s-prod-edge01`, then `radio-pi02`.
7. **Uncordon both nodes** — they were cordoned to pin CoreDNS to `radio-pi01`. Nothing
   reschedules until this is undone:

   ```bash
   kubectl --context EdgeSDR uncordon radio-pi02 k0s-prod-edge01.k0s.wsh.no
   ```

8. **Restore the default gateway** on radio-pi01:

   ```bash
   ssh root@10.20.13.21 /root/away-mode-gw.sh off
   ```

9. **Unpark the workloads by hand — Flux will not do it.** This is the inverse of the trap in
   [Before the next shutdown](#before-the-next-shutdown), and it bites the other way: `nodeSelector`
   is absent from git, so kustomize-controller never owns the field and the `away: "true"` key added
   by away-mode.md survives reconciliation forever. Sweep for it rather than counting pods:

   ```bash
   K="kubectl --context EdgeSDR"
   for k in deploy ds sts; do $K get $k -A      -o custom-columns=KIND:.kind,NS:.metadata.namespace,NAME:.metadata.name,SEL:.spec.template.spec.nodeSelector      | grep -i away; done
   ```

   Remove only the `away` key, so selectors the chart legitimately sets survive:

   ```bash
   P='[{"op":"remove","path":"/spec/template/spec/nodeSelector/away"}]'
   $K -n ceph-csi-edge-sdr      patch ds ceph-csi-rbd-nodeplugin                --type=json -p "$P"
   $K -n fluent-bit-edge-sdr    patch ds fluent-bit                             --type=json -p "$P"
   $K -n node-exporter-edge-sdr patch ds node-exporter-prometheus-node-exporter --type=json -p "$P"
   ```

   `node-exporter` also carries `kubernetes.io/os: linux` from its HelmRelease — that one stays.
   Removing the whole `nodeSelector` map would strip it too.

   **Do not verify this with `get pods | grep radio-pi01`.** A DaemonSet parked this way sits at
   `DESIRED 0`, so it contributes no Pending pod and no error anywhere — it is simply absent, and a
   pod count looks normal without it. On 2026-09-22 that is exactly what happened: `adsb-mqtt` and
   `tar1090` came back, the pod count looked right, and all three DaemonSets stayed parked for the
   rest of the day. The damage is quiet and cumulative: no ceph-rbd mounts anywhere on the cluster
   (the kubescape `storage` Pod cannot start, its aggregated API goes `MissingEndpoints`, and
   **every namespace deletion on the cluster then hangs in `Terminating`**), no host metrics, no log
   shipping. Use the sweep above, then confirm:

   ```bash
   $K get ds -A                                   # every DESIRED should be non-zero
   $K get csinode -o custom-columns=NAME:.metadata.name,DRIVERS:'.spec.drivers[*].name'
   ```

   k0s restores the stock CoreDNS deployment with two replicas on its own.

10. Re-check the SDR feeder stats pages. If ShipXplorer is still offline, it is the source-IP
    lock described in away-mode.md, not a feed fault.

## Before the next shutdown

**Flux strips the hibernation annotation. Suspend the Kustomization first.**

`cnpg.io/hibernation` is set with `kubectl annotate`, so it exists only in the live object — it is
not in git. On 2026-09-01 the hibernation completed cleanly at 05:47 (all 6 instance pods gone,
clean shutdown checkpoint written), and then `kustomize-controller` reconciled at **05:52:42Z** and
removed the annotation. Postgres was back up ten seconds later at 05:52:52 and was still running
when the VMs were powered off — an unclean stop on all three clusters, which is exactly the failure
the hibernation was meant to avoid. The default reconcile interval is 10m, so the window to power
off before Flux undoes the hibernation is nowhere near long enough to rely on.

Correct order:

```bash
K="kubectl --context Production"
flux --context Production suspend kustomization postgres-cnpg-production

$K -n postgres-production annotate cluster postgres-prod cnpg.io/hibernation=on --overwrite
$K -n postgres-test       annotate cluster cluttertestdb cnpg.io/hibernation=on --overwrite
$K -n postgres-test       annotate cluster testdb        cnpg.io/hibernation=on --overwrite

# MUST be 0 immediately before powering anything off - do not skip this
$K get pods -A -l cnpg.io/podRole=instance
```

Re-check that pod count right before the first VM goes down, not just once after annotating. If
instances have come back, Flux is not actually suspended.

On the way back, resume it after step 4:

```bash
flux --context Production resume kustomization postgres-cnpg-production
```

The same trap applies to anything else parked with a live-object-only edit. `nodeSelector` parking
on the edge cluster survived three weeks because the key is absent from git and Flux had no opinion
about it; an annotation on an object Flux _does_ manage is a different case, and loses.

## Deferred work parked until after the return

- journald cap on both Pis (~2.6 GB, moves radio-pi01 from 81% to ~72%)
- radio-pi01 SD swapfile -> zram (pi02 already uses zram; pi01 still runs `dphys-swapfile`)
