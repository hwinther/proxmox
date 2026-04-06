# Ceph CSI (RBD) — edge-sdr

Flux installs **`ceph-csi-rbd`** into **`ceph-csi-edge-sdr`**. Adjust monitors / `clusterID` / **`pool`** in [`ceph-csi-rbd-helmrelease.yaml`](ceph-csi-rbd-helmrelease.yaml) if this cluster differs from production.

The HelmRelease sets **`nodeplugin`** and **`provisioner`** tolerations for **`node-type=edge-sdr:NoSchedule`** so CSI pods schedule on Raspberry Pi edge workers (see [infra/k0s/raspberry-pi-worker.md](../../../../infra/k0s/raspberry-pi-worker.md)).

**Small clusters:** **`provisioner.replicaCount: 1`** — the chart’s pod anti-affinity cannot place two provisioners on one edge worker. **`nodeplugin.httpMetrics.enabled: false`** — with **hostNetwork**, the metrics port and **liveness-prometheus** both tried to bind the same host **:8080** (seen as `address already in use`).

## Pool: share with production or not?

**Sharing one pool (e.g. `k8s-rbd`)** is normal: both clusters get RBD images in the same pool; Kubernetes keeps volume identity separate per cluster. Downsides: shared capacity and one place to size/operate; if you ever need hard isolation (quotas, blast radius, “this pool is only edge”), use a **second pool** (e.g. `k8s-rbd-edge-sdr`) and point this HelmRelease’s **`storageClass.pool`** (and `csiConfig`) at it.

## User: do **not** share the CephX client with production

Use a **dedicated** Ceph user for edge-sdr so a leaked kube secret or compromise in one cluster does not expose the other’s key, and you can **revoke or rotate** per cluster.

Example (same shared pool `k8s-rbd` as prod):

```bash
ceph auth get-or-create client.csi-k8s-edge-sdr \
  mon 'profile rbd' \
  osd 'profile rbd pool=k8s-rbd' \
  mgr 'profile rbd'
```

If you use a **dedicated pool**, replace `pool=k8s-rbd` with that pool name and create the pool first (`ceph osd pool create …`, `ceph osd pool application enable … rbd`).

## Before Flux can succeed

1. **Ceph** — pool exists, user exists, FSID and mons reachable from **edge-sdr** nodes.

2. **Create the Kubernetes secret** (never commit keys to Git). Namespace is **`ceph-csi-edge-sdr`**; `userID` is the Ceph name **without** the `client.` prefix:

   ```bash
   kubectl create namespace ceph-csi-edge-sdr
   NS=ceph-csi-edge-sdr
   KEY=$(ceph auth get-key client.csi-k8s-edge-sdr)
   kubectl -n "$NS" create secret generic csi-rbd-secret \
     --from-literal=userID=csi-k8s-edge-sdr \
     --from-literal=userKey="$KEY" \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

3. If you changed **pool** or **clusterID** in the HelmRelease, commit and reconcile:  
   `flux reconcile helmrelease -n ceph-csi-edge-sdr ceph-csi-rbd`.

## Smoke test

```bash
kubectl get pods -n ceph-csi-edge-sdr
kubectl get storageclass ceph-rbd
```
