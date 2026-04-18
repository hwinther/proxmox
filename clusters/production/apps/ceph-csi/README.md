# Ceph CSI (RBD) — production

Flux installs **`ceph-csi-rbd`** into **`ceph-csi-production`**. This is separate from Proxmox Ceph itself: you still create pools and keys on the Ceph cluster first.

## Before Flux can succeed

1. **Ceph** (on Proxmox or shell with `ceph` CLI):
   - Pool for Kubernetes RBD, e.g. `k8s-rbd`, with `rbd` application enabled.
   - CephX user (example name `csi-k8s`):

     ```bash
     ceph auth get-or-create client.csi-k8s \
       mon 'profile rbd' \
       osd 'profile rbd pool=k8s-rbd' \
       mgr 'profile rbd'
     ```

   - Note **`ceph fsid`** and monitor addresses (often **`:3300`** for msgr2 on the public network). Use IPs your k0s nodes can reach (**ceph_public** in your network plan).

2. **Edit** [`ceph-csi-rbd-helmrelease.yaml`](ceph-csi-rbd-helmrelease.yaml):
   - Replace **`CHANGEME_CEPH_FSID`** with the real FSID in **both** `csiConfig[0].clusterID` and `storageClass.clusterID` (must match).
   - Replace the **`10.10.30.x:3300`** monitor list with your real mon IPs (trim to one line if you have a single mon).

3. **Create the Kubernetes secret** (never commit keys to Git):

   ```bash
   kubectl create namespace ceph-csi-production # Create the namespace first
   NS=ceph-csi-production
   KEY=$(ceph auth get-key client.csi-k8s)
   kubectl -n "$NS" create secret generic csi-rbd-secret \
     --from-literal=userID=csi-k8s \
     --from-literal=userKey="$KEY" \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

   `userID` must **not** include the `client.` prefix.

4. Commit the edited Helm values and let Flux reconcile, or `flux reconcile helmrelease -n ceph-csi-production ceph-csi-rbd`.

## Smoke test

```bash
kubectl get pods -n ceph-csi-production
kubectl get storageclass ceph-rbd
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ceph-rbd-test
  namespace: default
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: ceph-rbd
  resources:
    requests:
      storage: 1Gi
EOF
kubectl get pvc ceph-rbd-test -n default
```

## Upgrades

Bump **`spec.chart.spec.version`** in the HelmRelease when you want a new chart. Read the chart [release notes](https://github.com/ceph/ceph-csi) for CSI/Kubernetes/Ceph version support.
