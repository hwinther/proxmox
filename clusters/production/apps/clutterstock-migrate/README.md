# Clutterstock SQLite migration (production)

The migrator **shares the same RWO PVC** (`ceph-rbd`) as `clutterstock-api`. Only one workload can attach that volume at a time.

## Before reconciling migrate

1. **Scale API to zero** so the volume detaches:

   ```bash
   kubectl -n clutterstock-production scale deployment clutterstock-api --replicas=0
   kubectl -n clutterstock-production rollout status deployment/clutterstock-api --timeout=120s
   ```

2. Ensure **PVC is Bound** and **CSI** is healthy:

   ```bash
   kubectl -n clutterstock-production get pvc clutterstock-api-sqlite
   ```

3. Reconcile and watch the Job:

   ```bash
   flux reconcile kustomization clutterstock-migrate -n flux-system --with-source
   kubectl -n clutterstock-production wait job/clutterstock-migrate-v097 --for=condition=complete --timeout=300s
   ```

4. **Scale API back**:

   ```bash
   kubectl -n clutterstock-production scale deployment clutterstock-api --replicas=1
   ```

## New migration image / reruns

Kubernetes **Job** pod templates are immutable. Bump `metadata.name` in [`job.yaml`](job.yaml) (e.g. `v097` → `v098`) when you change the migrator image or job spec, then reconcile. Delete old completed Jobs if names clash with TTL.

## If you still see `SQLite Error 14`

- Confirm no other pod mounts `clutterstock-api-sqlite` (`kubectl get pods -A -o json | jq` or describe PVC events).
- Check Job logs and `kubectl describe pod` for volume mount / **Multi-Attach** warnings.
