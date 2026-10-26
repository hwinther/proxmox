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
`.status.state` is `Completed`.

## If it stalls

- The plan status names the node and the reason (download, checksum, restart).
- Alpine controllers run k0s under OpenRC. If a node has the new binary but the service didn't come back:
  `rc-service k0scontroller restart` (or `k0sworker`) on that node.
- After an upgrade that also brought OS package updates, reboot Alpine nodes so the running kernel
  matches `/lib/modules` (see the NFS/nfsv4 kernel-module incident).
- To abandon a plan: `kubectl delete plan autopilot`. Nodes already upgraded stay upgraded.
