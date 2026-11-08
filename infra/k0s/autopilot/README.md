# k0s Autopilot upgrades

Both clusters were installed by hand (no k0sctl). Autopilot is built into k0s and already active on
both: the `plans` / `controlnodes` / `updateconfigs` CRDs exist and every controller is registered as a
`ControlNode`. Upgrades are done with a `Plan` per target version, committed here for review and
history and **applied by hand**. A Plan is a one-shot singleton (it must be named `autopilot`, and a
completed Plan is never re-executed), so Flux does not reconcile this directory.

Order: edge-sdr first (small cluster, single controller), then production, one minor at a time.

## Before applying

1. Every listed node exists, and there are no leftover records from renamed or rebuilt nodes:

   ```bash
   kubectl --context <ctx> get nodes
   kubectl --context <ctx> get controlnodes   # must list exactly the live controllers
   ```

   A stale `ControlNode` makes the Plan wait forever for a node that no longer exists.

2. No previous Plan is still present: `kubectl --context <ctx> get plan autopilot`. Delete a completed
   one first; a new id alone doesn't make Autopilot run it.
3. Cluster healthy: all Flux Kustomizations/HelmReleases Ready, all nodes Ready.
4. Take a backup on a controller: `sudo k0s backup --save-path /root/`.
5. The `url`s and `sha256`s match the release's `sha256sums.txt`, for every platform in the cluster
   (`linux-amd64` for the Alpine VMs, `linux-arm64` for the Pis).

## Apply and watch

```bash
kubectl --context EdgeSDR apply -f infra/k0s/autopilot/edge-sdr-v1.35.8.yaml
kubectl --context EdgeSDR get plan autopilot -o yaml   # .status.state and per-node status
kubectl --context EdgeSDR get nodes -w                 # kubelet versions change node by node
```

Controllers upgrade first, then workers (`limits.concurrent: 1`). The plan is done when
`.status.state` is `Completed`. **Autopilot does not follow the order of the `nodes:` lists**: on
2026-11-08 edge did radio-pi02 before pi01, and production did prod03, prod02, prod01, then
prod05 before prod04. Never rely on "node X goes first"; prepare every node before applying.

**Autopilot cordons and drains every node it upgrades**, controllers included: all non-DaemonSet
pods on the node are evicted and rescheduled elsewhere, and Kubernetes does not move them back
afterwards. A drain stalls on any PodDisruptionBudget that allows 0 disruptions.

Expected transient states (seen in the edge-sdr run, 2026-10-27, ~14 min end to end):

- A node shows `Ready=Unknown` for a minute while k0s restarts on the new binary.
- `konnectivity-agent` sits in `ContainerCreating` while the node pulls the new image (slow on Pis).
- Pods pinned to a node (the SDR feeders, by USB dongle) stay Pending until that node is schedulable
  again, then fail one startup probe while binding ports.

## 1.35 -> 1.36 (extra steps)

Plans: `edge-sdr-v1.36.6.yaml`, then `production-v1.36.6.yaml`. Delete the completed 1.35.8 Plan in
each cluster first (`kubectl delete plan autopilot`).

**1. Cilium 1.20 before k0s 1.36 (production only): DONE 2026-11-08.** Cilium 1.19 is only tested
against Kubernetes 1.32–1.35, and 1.20 is the first release that covers 1.36. Production went
1.19.4 → 1.19.10 → 1.20.4 on 1.35, and Cilium is now a Flux HelmRelease
(`clusters/production/apps/cilium/`, #951/#953), no longer a k0s extension. Before applying the
Plan, just confirm: `kubectl -n kube-system get hr cilium` is Ready on chart 1.20.x and every agent
reports `cilium-dbg version` 1.20.x. The edge cluster runs kube-router and skips this step.

**2. containerd drop-ins must use the v3 format.** k0s 1.36 ships containerd 2.3 (we are on
1.7.35). Its pre-flight refuses to start k0s when any file in `/etc/k0s/containerd.d/` has
`version = 2` or references the old `io.containerd.grpc.v1.cri` plugin. The Pis have one:
`device-ownership.toml` (see `../raspberry-pi-worker.md`). Check every node for others:
`ls /etc/k0s/containerd.d/` and `head -1 /etc/k0s/containerd.toml` (must still be `# k0s_managed=true`).
Checked 2026-11-08: prod01–05 and edge01 have **no** drop-ins and a k0s-managed `containerd.toml`,
so only the Pis need the swap below.

containerd 1.7 can't read the v3 format, so the file can't simply be rewritten ahead of time.
On **all** Pis, **before applying the Plan** (Autopilot picks the worker order itself; on 2026-11-08
pi02 went first while only pi01 had been prepared, and k0s 1.36 refused to start on it:
`pre-flight checks failed ... expected 3, got 2`):

```bash
sudo mv /etc/k0s/containerd.d/device-ownership.toml /root/device-ownership.toml.v2
```

Running containers keep their devices; k0s reloads containerd without the drop-in. Right **after**
the Pi reports v1.36.6:

```bash
sudo tee /etc/k0s/containerd.d/device-ownership.toml >/dev/null <<'TOML'
version = 3
[plugins."io.containerd.cri.v1.runtime"]
  device_ownership_from_security_context = true
TOML
grep -r device_ownership /run/k0s/   # must say true
# decoders reopen their dongle (readsb in adsb-edge-sdr, ais-catcher in ais-catcher-edge-sdr)
kubectl -n adsb-edge-sdr delete pod -l app.kubernetes.io/name=readsb --field-selector spec.nodeName=<pi>
kubectl -n ais-catcher-edge-sdr delete pod --field-selector spec.nodeName=<pi>
```

Between the two steps, decoders that start as uid 65532 can't open their dongle (`usb_open error -3`).
That's expected: those pods restart anyway during the drain.

If a Pi was missed and its k0s fails the pre-flight check, write the v3 file right away (the new
binary is already in place) and `systemctl restart k0sworker`; it comes back in about a minute.

**3. ceph-csi 3.17.1 or newer** (3.17.0 is only tested up to 1.35): both clusters already run
3.18.2 (#849, 2026-11-08), so nothing to do. 3.18's image needs x86-64-v3 (AVX2), which every k0s VM
has had since 2026-11-08 (prod01/edge01 on `cpu: host`, prod02 moved to shuttle03). Any new k0s VM
must also get an AVX2 CPU type, or its nodeplugin crash-loops.

Kyverno 1.19 lists 1.33–1.35 as tested ("other versions may work"); CNPG 1.30 supports 1.36.

## Production

Same flow, plus four things the edge cluster doesn't have.

**1. CNPG primaries and their replicas.** Each CNPG cluster has a `<cluster>-primary` PDB with
`minAvailable: 1` over a single pod, so a primary can't be evicted. CNPG handles this itself: when
the primary's node is cordoned, it switches over to a ready replica, and the drain continues. In
the 2026-10-27 production run, every cluster switched without help.

What goes wrong is **where the replicas land**:

- An evicted replica can only reschedule onto a schedulable node. Early in the run, that is
  often the node Autopilot does next.
- When that node is cordoned, the primary and its replica sit on it together, so CNPG has
  nothing to switch to and the drain hangs.
- In 2026-10-27, after prod01 was drained, all three replicas landed on prod02 (next in line),
  and one was still stuck mounting its ceph-rbd volume.

So after each node completes, check where the CNPG pods are. If a replica sits on a node that
hasn't been upgraded yet, cordon that node early (Autopilot uncordons it when it's done with it)
and delete the replica pod. It comes back on an upgraded node, as long as one is schedulable:

```bash
kubectl --context Production get pods -A -l cnpg.io/cluster \
  -o custom-columns=POD:.metadata.name,ROLE:.metadata.labels.role,READY:.status.containerStatuses[0].ready,NODE:.spec.nodeName
kubectl --context Production cordon <next-node>
kubectl --context Production -n <ns> delete pod <replica-pod>
```

ceph-rbd volumes can take 3+ minutes to mount on the new node: you may see a Multi-Attach error,
then `MountDevice ... DeadlineExceeded` or `operation ... already exists`. If a pod stays Pending
on a node about to be drained, delete it again rather than wait.

If a cluster doesn't switch over by itself, do it by hand. There's no `kubectl cnpg` plugin; this
is what `cnpg promote` does:

```bash
# Which primaries are on the cordoned node?
kubectl --context Production get pods -A -l cnpg.io/instanceRole=primary -o wide
# Promote the replica on another node, then wait for status.currentPrimary to match.
kubectl --context Production -n postgres-production patch cluster postgres-prod \
  --subresource=status --type=merge -p '{"status":{"targetPrimary":"postgres-prod-1"}}'
kubectl --context Production -n postgres-production get cluster postgres-prod \
  -o jsonpath='{.status.currentPrimary} {.status.phase}{"\n"}'
```

Do one cluster at a time and wait for `Cluster in healthy state` before the next. There is no WAL
archive, so an old primary rejoining as a replica relies on pg_rewind. If a replica hangs at
"Consistent recovery state has not been yet reached", run `SELECT pg_switch_wal();` on the primary
(see the CNPG rewind/idle-primary notes).

**2. Capacity.** Draining the 8-core prod01 puts roughly 4 cores and 9 GiB of requests on the other
nodes; prod04 is already near its memory requests. Some pods may sit Pending briefly. After the plan
completes, rebalance (rollout restart of movable workloads, never the CNPG or RabbitMQ members).

**3. RabbitMQ** has a PDB (`maxUnavailable: 1`, `rabbitmq-production/pdb-rabbitmq.yaml`) so a drain
can't take two of the three members down at once. Check it exists before applying:
`kubectl --context Production -n rabbitmq-production get pdb`.

**4. The kubeconfig points at prod01.** Its API server goes away while prod01 restarts, so watch
loops should use another controller: `--server https://10.20.13.13:6443` (or `.12`).

Expect alert noise while it runs (node cordoned, pods restarting, the aggregated-API alerts during
controller restarts).

Seen in the 2026-10-27 production run (22:12–22:25, ~13 min):

- Order: prod03, prod01, prod02 (controllers), then prod04, prod05.
- prod01 went `Ready=Unknown` for about a minute after its upgrade and came back by itself.
- Afterwards:
  - `kyverno-policies` failed its dry-run until the Kyverno admission controller was back; a
    reconcile fixed it.
  - A few pods were left in `Error` from the evictions.
  - Requests were unbalanced: prod02 at 95% CPU, prod05 at 10%.

Seen in the 2026-11-08 production run (1.35.8 → 1.36.6, 17:15–17:23, ~8 min):

- Order: prod03, prod02, prod01, prod05, prod04 (not the list order).
- Cordoning the next controller early (prod01, which held all three CNPG primaries) made CNPG
  switch every primary over before its drain, and no drain hung.
- **Stale rbd mappings:** three RWO pods that moved during the drains (ddnsadmin production/test,
  grafana) stuck in `ContainerCreating` on the new node with
  `MountVolume.MountDevice failed ... rbd image ... is still being used`. The old node kept a
  kernel rbd mapping (not mounted, no holders) because k0s/kubelet restarted before NodeUnstage.
  Fix, per volume:

  ```bash
  # image name of the PV, then the watcher (10.20.4.1x = prod0x storage NIC), on a PVE Ceph host:
  kubectl get pv <pv> -o jsonpath='{.spec.csi.volumeAttributes.imageName}'
  rbd status k8s-rbd/<image>
  # on that old node: find the device, confirm it is not mounted, unmap it
  grep -l <image> /sys/bus/rbd/devices/*/name; grep /dev/rbd<N> /proc/mounts
  echo <N> > /sys/bus/rbd/remove_single_major   # rbd is loaded with single_major=Y: plain `remove` gives EINVAL
  ```

  Kubelet's next retry mounts within a minute. After every run, list `ContainerCreating` pods with
  PVCs before calling it done.
- Requests ended at prod03 92% CPU/93% memory, prod04 3%. Rebalance as in **2. Capacity**.

## If it stalls

- The plan status names the node and the reason (download, checksum, restart).
- Alpine controllers run k0s under OpenRC. If a node has the new binary but the service didn't come back:
  `rc-service k0scontroller restart` (or `k0sworker`) on that node.
- After an upgrade that also brought OS package updates, reboot Alpine nodes so the running kernel
  matches `/lib/modules` (see the NFS/nfsv4 kernel-module incident).
- To abandon a plan: `kubectl delete plan autopilot`. Nodes already upgraded stay upgraded.
