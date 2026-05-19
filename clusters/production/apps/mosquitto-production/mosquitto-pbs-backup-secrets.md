# Proxmox Backup Server credentials (`mosquitto-production`)

The backup CronJob loads env vars from the Kubernetes Secret
**`mosquitto-pbs-backup`** in namespace **`mosquitto-production`**. Create it
with `kubectl`. Do not commit real values to git.

The cluster-wide PBS encryption keyfile lives in `platform-production` and is
cloned here automatically — see
[`../platform-production/pbs-encryption-keyfile.md`](../platform-production/pbs-encryption-keyfile.md).
The clone needs this namespace's Kyverno RBAC
(`kyverno-rbac-generate-pbs-encryption-keyfile.yaml`) **and** a clone rule in
`../platform-production/kyverno-clusterpolicy-clone-pbs-encryption-keyfile.yaml`.

## ⚠️ Two-push ordering (hard requirement)

The clone ClusterPolicy's validate-policy webhook **denies the whole policy** if
a target namespace's Kyverno RBAC isn't already live. So land this in **two
separate commits/pushes**:

1. **Push 1:** this app dir incl. `kyverno-rbac-generate-pbs-encryption-keyfile.yaml`
   + the CronJob. Let Flux reconcile so the RBAC RoleBinding is live.
2. **Push 2:** the new `clone-to-mosquitto-production` rule appended to the
   platform-production ClusterPolicy.

Adding both in one commit dry-run-fails the ClusterPolicy and blocks the Flux
Kustomization. Until the keyfile is cloned the CronJob still runs (mount is
`optional: true`) but **unencrypted**.

## Required keys

| Key              | Purpose                                                              |
| ---------------- | -------------------------------------------------------------------- |
| `PBS_REPOSITORY` | Repository string for `proxmox-backup-client`.                       |
| `PBS_PASSWORD`   | Password or API token secret value.                                  |

## Optional keys

| Key                       | When to set                                                                                |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| `PBS_FINGERPRINT`         | Self-signed PBS or pinned cert fingerprint.                                                 |
| `PBS_NAMESPACE`           | PBS datastore namespace (e.g. `Production/mosquitto`). Job appends `--ns`. Create it in the PBS UI first. |
| `PBS_ENCRYPTION_PASSWORD` | **Always set** — the cluster `pbs-encryption-keyfile` is passphrase-protected (project convention). |
| `PBS_RESTORE_SNAPSHOT`    | Only for a manual restore: full snapshot path.                                             |

## Create the Secret

```bash
kubectl -n mosquitto-production create secret generic mosquitto-pbs-backup \
  --from-literal=PBS_REPOSITORY='user@pbs!tokenid@pbs.example.com:8007:datastore' \
  --from-literal=PBS_PASSWORD='your-api-token-uuid-here' \
  --from-literal=PBS_NAMESPACE='Production/mosquitto' \
  --from-literal=PBS_ENCRYPTION_PASSWORD='<pbs-encryption-keyfile passphrase>'
```

## Trigger an out-of-schedule backup

```bash
kubectl -n mosquitto-production create job \
  --from=cronjob/mosquitto-pbs-backup mosquitto-pbs-backup-manual-$(date +%s)
```

## Restore (manual, destructive — outline)

```bash
kubectl -n mosquitto-production patch secret mosquitto-pbs-backup --type merge \
  -p '{"stringData":{"PBS_RESTORE_SNAPSHOT":"host/mosquitto/<ts>"}}'
kubectl -n mosquitto-production scale statefulset mosquitto --replicas=0
kubectl -n mosquitto-production wait --for=delete pod -l app=mosquitto --timeout=120s
# restore data.pxar into the PVC via a one-off proxmox-backup-client restore Job
# (mirror home-assistant-pbs-restore-job.yaml), then:
kubectl -n mosquitto-production scale statefulset mosquitto --replicas=1
```
