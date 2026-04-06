# Kubescape operator — edge-sdr

Flux installs the **kubescape-operator** chart into **`kubescape-edge-sdr`**. The HelmRelease **`dependsOn`** [`ceph-csi-rbd`](../ceph-csi/ceph-csi-rbd-helmrelease.yaml) so CSI is usually ready first; **`persistence.storageClass`** is set to **`ceph-rbd`** explicitly.

## PVCs stuck Pending (CSI / StorageClass not ready yet)

If the chart ran before **Ceph CSI** installed the default **`ceph-rbd`** `StorageClass` or before **`csi-rbd-secret`** existed, PersistentVolumeClaims can stay **Pending** forever. Kubernetes does not retroactively bind those claims.

1. Confirm CSI is healthy: `kubectl get pods -n ceph-csi-edge-sdr`, `kubectl get storageclass ceph-rbd`.
2. List claims: `kubectl get pvc -n kubescape-edge-sdr`.
3. **Delete workloads using the PVCs**, then the **PVCs** (order matters if pods are still running):

   ```bash
   NS=kubescape-edge-sdr
   kubectl get statefulset,deployment,pod -n "$NS"
   # Scale down or delete pods that mount the stuck PVCs, then:
   kubectl delete pvc -n "$NS" --all
   ```

   If a **StatefulSet** owns volume claim templates, delete the StatefulSet (Helm/Flux will recreate it on reconcile) or delete pods one-by-one after deleting PVCs so the STS creates new claims.

4. Reconcile: `flux reconcile helmrelease -n kubescape-edge-sdr kubescape --with-source`

Scan/cache data on recreated volumes starts empty; that is expected after storage recovery.
