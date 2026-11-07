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

## 1.35 -> 1.36 (extra steps)

Plans: `edge-sdr-v1.36.6.yaml`, then `production-v1.36.6.yaml`. Delete the completed 1.35.8 Plan in
each cluster first (`kubectl delete plan autopilot`).

**1. Cilium 1.20 before k0s 1.36 (production only).** Cilium 1.19 is only tested against Kubernetes
1.32–1.35; 1.20 is the first release that covers 1.36 (and still covers 1.35), so upgrade Cilium
first, on 1.35. Cilium is a k0s Helm extension (`spec.extensions.helm.charts` in
`/etc/k0s/k0s.yaml` on prod01–03), not a Flux HelmRelease. The edge cluster runs kube-router and
skips this step.

- Go to the latest 1.19 patch first (Cilium's upgrade guide asks for it), then 1.20.x.
- For each step, change `version:` of the `cilium` chart in `/etc/k0s/k0s.yaml` on **all three**
  controllers, then restart `k0scontroller` on them one at a time. The leader applies the Chart CR;
  check `kubectl -n kube-system get charts.helm.k0sproject.io k0s-addon-chart-cilium -o jsonpath='{.status.appVersion}'`
  and `kubectl -n kube-system rollout status ds/cilium`.
- Run Cilium's pre-flight check for 1.20 first (`helm template cilium/cilium --version <1.20.x>
  --namespace kube-system --set preflight.enabled=true --set agent=false --set operator.enabled=false
  --set k8sServiceHost=127.0.0.1 --set k8sServicePort=7443`), wait until the pre-flight DaemonSet is
  fully Ready and the `cnp-validator` passes, then delete it.
- 1.20 notes checked against our values (2026-11-07): nothing we set was renamed or removed. Policy
  changes: no CNP uses Kafka/`l7proto` rules or `toServices`; empty CNPs are rejected on admission.

**2. containerd drop-ins must use the v3 format.** k0s 1.36 ships containerd 2.3 (we are on
1.7.35). Its pre-flight refuses to start k0s when any file in `/etc/k0s/containerd.d/` has
`version = 2` or references the old `io.containerd.grpc.v1.cri` plugin. The Pis have one:
`device-ownership.toml` (see `../raspberry-pi-worker.md`). Check every node for others:
`ls /etc/k0s/containerd.d/` and `head -1 /etc/k0s/containerd.toml` (must still be `# k0s_managed=true`).

containerd 1.7 can't read the v3 format, so the file can't simply be rewritten ahead of time. On
each Pi, just **before** Autopilot reaches it (watch the Plan status; pi01 goes first):

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

**3. ceph-csi 3.17.1 or newer** (3.17.0 is only tested up to 1.35): bumped to 3.17.2 in the same PR
as these plans. Let Flux roll it out before applying the Plans. Don't go to 3.18 (needs x86-64-v3).

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

## If it stalls

- The plan status names the node and the reason (download, checksum, restart).
- Alpine controllers run k0s under OpenRC. If a node has the new binary but the service didn't come back:
  `rc-service k0scontroller restart` (or `k0sworker`) on that node.
- After an upgrade that also brought OS package updates, reboot Alpine nodes so the running kernel
  matches `/lib/modules` (see the NFS/nfsv4 kernel-module incident).
- To abandon a plan: `kubectl delete plan autopilot`. Nodes already upgraded stay upgraded.
