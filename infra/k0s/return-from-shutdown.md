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

9. Flux restores the parked workloads by itself (`adsb-mqtt`, `tar1090`, `fluent-bit`,
   `node-exporter`, `ceph-csi-rbd-nodeplugin`), and k0s restores the stock CoreDNS deployment with
   two replicas. None of the parking edits are in git, so there is nothing to revert manually.

   ```bash
   kubectl --context EdgeSDR get pods -A -o wide | grep radio-pi01   # expect ~14 pods
   ```

   If anything stays parked, Flux is suspended or failing — investigate rather than re-patching.

10. Re-check the SDR feeder stats pages. If ShipXplorer is still offline, it is the source-IP
    lock described in away-mode.md, not a feed fault.

## Deferred work parked until after the return

- journald cap on both Pis (~2.6 GB, moves radio-pi01 from 81% to ~72%)
- radio-pi01 SD swapfile -> zram (pi02 already uses zram; pi01 still runs `dphys-swapfile`)
