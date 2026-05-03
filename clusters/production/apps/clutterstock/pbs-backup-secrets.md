# Proxmox Backup Server credentials (`clutterstock-production`)

The backup and restore Jobs load environment variables from the Kubernetes Secret **`clutterstock-pbs-backup`** in namespace **`clutterstock-production`**. Create and update it with `kubectl` (or SealedSecrets / External Secrets / your usual secret workflow). Do not commit real values to git.

The cluster-wide PBS encryption keyfile lives in `platform-production` and is cloned here automatically — see [`../platform-production/pbs-encryption-keyfile.md`](../platform-production/pbs-encryption-keyfile.md).

## Required keys

| Key              | Purpose                                                                                                                                 |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `PBS_REPOSITORY` | Default repository string for `proxmox-backup-client` (user, host, port, datastore).                                                    |
| `PBS_PASSWORD`   | Password or API token secret value. See [Environment variables](https://pbs.proxmox.com/docs/backup-client.html#environment-variables). |

## Optional keys

| Key                       | When to set                                                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `PBS_FINGERPRINT`         | Self-signed PBS or pinned cert fingerprint.                                                                                                                                                                  |
| `PBS_NAMESPACE`           | PBS datastore namespace (e.g. `Production/clutterstock`). Job appends `--ns $PBS_NAMESPACE` to backup and restore. Restores must use the same value as the backup. Create the namespace in the PBS UI first. |
| `PBS_ENCRYPTION_PASSWORD` | Only when the keyfile is password-protected. Read from env by `proxmox-backup-client`.                                                                                                                       |
| `PBS_RESTORE_SNAPSHOT`    | Only for **restore**: full snapshot path (e.g. `host/clutterstock-postgres/2026-05-04T03:00:00Z`).                                                                                                           |

## Create the Secret

```bash
kubectl -n clutterstock-production create secret generic clutterstock-pbs-backup \
  --from-literal=PBS_REPOSITORY='user@pbs!tokenid@pbs.example.com:8007:datastore' \
  --from-literal=PBS_PASSWORD='your-api-token-uuid-here' \
  --from-literal=PBS_NAMESPACE='Production/clutterstock'
```

Add `PBS_ENCRYPTION_PASSWORD` and/or `PBS_FINGERPRINT` literals as needed.

## Add or change an optional key (`PBS_NAMESPACE`, `PBS_ENCRYPTION_PASSWORD`, `PBS_RESTORE_SNAPSHOT`, `PBS_FINGERPRINT`)

**Patch (merge), keeping existing keys untouched:**

```bash
kubectl -n clutterstock-production patch secret clutterstock-pbs-backup --type merge -p '{
  "stringData": {
    "PBS_NAMESPACE": "Production/clutterstock",
    "PBS_ENCRYPTION_PASSWORD": "<keyfile-password>"
  }
}'
```

Set a value to `null` in the same patch to remove a key. The next scheduled CronJob run picks up the new env automatically — env from a Secret is read at pod start, so already-running pods are not affected. To validate the change before the next scheduled run, trigger an out-of-band Job from the CronJob:

```bash
kubectl -n clutterstock-production create job --from=cronjob/clutterstock-pbs-backup clutterstock-pbs-backup-manual-$(date +%s)
```

## Restore (manual, destructive)

The restore Job is intentionally **not** in `kustomization.yaml` so Flux doesn't re-run it on reconcile. Apply manually:

```bash
# 1. Set the snapshot path to restore from
kubectl -n clutterstock-production patch secret clutterstock-pbs-backup --type merge \
  -p '{"stringData":{"PBS_RESTORE_SNAPSHOT":"host/clutterstock-postgres/2026-05-04T03:00:00Z"}}'

# 2. Stop the API (writes during restore would conflict with --clean drops)
kubectl -n clutterstock-production scale deployment clutterstock-api --replicas=0

# 3. Run the restore
kubectl apply -f clusters/production/apps/clutterstock/clutterstock-pbs-restore-job.yaml

# 4. Watch it
kubectl -n clutterstock-production get job clutterstock-pbs-restore-v001 -w

# (the restore is still a one-shot Job, not a CronJob — version-bump pattern still applies for re-runs)

# 5. Bring the API back up
kubectl -n clutterstock-production scale deployment clutterstock-api --replicas=1

# 6. Optional: clear PBS_RESTORE_SNAPSHOT so it's not stale next time
kubectl -n clutterstock-production patch secret clutterstock-pbs-backup --type merge \
  -p '{"stringData":{"PBS_RESTORE_SNAPSHOT":null}}'
```

`pg_restore --clean --if-exists --no-owner --no-acl` drops and recreates objects owned by the `clutterstock` role inside the database — verify on a clone first if there's any doubt.

## Verify (without printing secret values)

```bash
kubectl -n clutterstock-production describe secret clutterstock-pbs-backup
```

`describe` lists each data key and byte size, not the decoded values.
