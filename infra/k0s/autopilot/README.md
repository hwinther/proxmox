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

**Autopilot cordons and drains every node it upgrades**, controllers included: all non-DaemonSet
pods on the node are evicted and rescheduled elsewhere, and Kubernetes does not move them back
afterwards. A drain stalls on any PodDisruptionBudget that allows 0 disruptions.

Expected transient states (seen in the edge-sdr run, 2026-10-27, ~14 min end to end):

- A node shows `Ready=Unknown` for a minute while k0s restarts on the new binary.
- `konnectivity-agent` sits in `ContainerCreating` while the node pulls the new image (slow on Pis).
- Pods pinned to a node (the SDR feeders, by USB dongle) stay Pending until that node is schedulable
  again, then fail one startup probe while binding ports.

## Production

Same flow, plus three things the edge cluster doesn't have.

**1. CNPG primaries block drains.** Each CNPG cluster has a `<cluster>-primary` PDB with
`minAvailable: 1` over a single pod, so evicting a primary is refused and the plan hangs on that
node. When the plan cordons a node that hosts a primary, switch that cluster over to its replica on
a node that is schedulable (there's no `kubectl cnpg` plugin; this is what `cnpg promote` does):

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

Expect alert noise while it runs (node cordoned, pods restarting, the aggregated-API alerts during
controller restarts).

## If it stalls

- The plan status names the node and the reason (download, checksum, restart).
- Alpine controllers run k0s under OpenRC. If a node has the new binary but the service didn't come back:
  `rc-service k0scontroller restart` (or `k0sworker`) on that node.
- After an upgrade that also brought OS package updates, reboot Alpine nodes so the running kernel
  matches `/lib/modules` (see the NFS/nfsv4 kernel-module incident).
- To abandon a plan: `kubectl delete plan autopilot`. Nodes already upgraded stay upgraded.
