# Proxmox Backup Server credentials (`home-assistant-production`)

The backup CronJob and restore Job load environment variables from the Kubernetes Secret **`home-assistant-pbs-backup`** in namespace **`home-assistant-production`**. Create/update it with `kubectl`. Do not commit real values to git.

The cluster-wide PBS encryption keyfile lives in `platform-production` and is cloned here automatically — see [`../platform-production/pbs-encryption-keyfile.md`](../platform-production/pbs-encryption-keyfile.md). The clone requires this namespace's Kyverno RBAC (`kyverno-rbac-generate-pbs-encryption-keyfile.yaml`) and a clone rule in `kyverno-clusterpolicy-clone-pbs-encryption-keyfile.yaml`.

## Required keys

| Key              | Purpose                                                                             |
| ---------------- | ----------------------------------------------------------------------------------- |
| `PBS_REPOSITORY` | Repository string for `proxmox-backup-client` (user, host, port, datastore).         |
| `PBS_PASSWORD`   | Password or API token secret value.                                                  |

## Optional keys

| Key                       | When to set                                                                                                              |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `PBS_FINGERPRINT`         | Self-signed PBS or pinned cert fingerprint.                                                                               |
| `PBS_NAMESPACE`           | PBS datastore namespace (e.g. `Production/home-assistant`). Job appends `--ns`. Restores must use the same value. Create the namespace in the PBS UI first. |
| `PBS_ENCRYPTION_PASSWORD` | **Always set** — the cluster `pbs-encryption-keyfile` is passphrase-protected (project convention).                       |
| `PBS_RESTORE_SNAPSHOT`    | Only for **restore**: full snapshot path (e.g. `host/home-assistant/2026-05-16T04:00:00Z`).                              |

> **The encryption key itself is not a key in this Secret.** The AES-256-GCM keyfile
> is the cluster-wide Secret `pbs-encryption-keyfile` in `platform-production`, cloned
> into this namespace by Kyverno and mounted at `/etc/pbs/keyfile`. The Job adds
> `--keyfile` only if that file exists (mount is `optional: true`): no keyfile → backups
> run **unencrypted**; keyfile present → encrypted automatically. Our cluster keyfile is
> passphrase-protected, so `PBS_ENCRYPTION_PASSWORD` is **always** set in this Secret. See
> [`../platform-production/pbs-encryption-keyfile.md`](../platform-production/pbs-encryption-keyfile.md).

## Create the Secret

```bash
kubectl -n home-assistant-production create secret generic home-assistant-pbs-backup \
  --from-literal=PBS_REPOSITORY='user@pbs!tokenid@pbs.example.com:8007:datastore' \
  --from-literal=PBS_PASSWORD='your-api-token-uuid-here' \
  --from-literal=PBS_NAMESPACE='Production/home-assistant' \
  --from-literal=PBS_ENCRYPTION_PASSWORD='<pbs-encryption-keyfile passphrase>'
```

Patch (merge) to add/change a key; set a value to `null` to remove it. Env from a Secret is not re-read by a running pod — the next scheduled CronJob run picks up changes.

## Trigger an out-of-schedule backup

```bash
kubectl -n home-assistant-production create job \
  --from=cronjob/home-assistant-pbs-backup home-assistant-pbs-backup-manual-$(date +%s)
```

## Restore (manual, destructive)

The restore Job is intentionally **not** in `kustomization.yaml`.

```bash
# 1. Snapshot to restore from
kubectl -n home-assistant-production patch secret home-assistant-pbs-backup --type merge \
  -p '{"stringData":{"PBS_RESTORE_SNAPSHOT":"host/home-assistant/2026-05-16T04:00:00Z"}}'

# 2. Stop HA (frees the RWO volume)
kubectl -n home-assistant-production scale statefulset home-assistant --replicas=0
kubectl -n home-assistant-production wait --for=delete pod -l app=home-assistant --timeout=120s

# 3. (optional) empty the PVC first for a clean restore — restore does not delete
#    files absent from the snapshot. Use the seed-pod technique if needed.

# 4. Run the restore (bump metadata.name first if v001 already ran)
kubectl apply -f clusters/production/apps/home-assistant-production/home-assistant-pbs-restore-job.yaml

# 5. Bring HA back up
kubectl -n home-assistant-production scale statefulset home-assistant --replicas=1
```

## Verify (without printing secret values)

```bash
kubectl -n home-assistant-production describe secret home-assistant-pbs-backup
```
