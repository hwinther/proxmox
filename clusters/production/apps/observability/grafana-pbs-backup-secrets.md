# Proxmox Backup Server credentials (`observability-production`)

The `grafana-pbs-backup` CronJob loads environment variables from the Kubernetes Secret **`grafana-pbs-backup`** in namespace **`observability-production`**. Create and update it with `kubectl`. Do not commit real values to git.

The cluster-wide PBS encryption keyfile lives in `platform-production` and is cloned here automatically — see [`../platform-production/pbs-encryption-keyfile.md`](../platform-production/pbs-encryption-keyfile.md). The clone is triggered by the `pbs.wsh.no/encryption-keyfile: "true"` label on the namespace.

## Required keys

| Key              | Purpose                                                                                                                                 |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `PBS_REPOSITORY` | Default repository string for `proxmox-backup-client` (user, host, port, datastore).                                                    |
| `PBS_PASSWORD`   | Password or API token secret value. See [Environment variables](https://pbs.proxmox.com/docs/backup-client.html#environment-variables). |

## Optional keys

| Key                       | When to set                                                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `PBS_FINGERPRINT`         | Self-signed PBS or pinned cert fingerprint.                                                                                                                                                                  |
| `PBS_NAMESPACE`           | PBS datastore namespace — `Production/k0s` for all k0s-cluster backups (shared across apps; per-app snapshots are distinguishable by the `hostname` in the CronJob spec — here `grafana-postgres`). Already exists on both local and remote PBS instances, no per-app namespace setup needed. |
| `PBS_ENCRYPTION_PASSWORD` | Required because the cluster keyfile is passphrase-protected. Read from env by `proxmox-backup-client`.                                                                                                      |

## Create the Secret

All k0s-cluster backups go into the shared `Production/k0s` PBS namespace (already created on both local and remote PBS instances). Per-app snapshots are kept distinct inside the namespace by each CronJob's `hostname` field (here `grafana-postgres`).

```bash
kubectl -n observability-production create secret generic grafana-pbs-backup \
  --from-literal=PBS_REPOSITORY='user@pbs!tokenid@pbs.example.com:8007:datastore' \
  --from-literal=PBS_PASSWORD='your-api-token-uuid-here' \
  --from-literal=PBS_NAMESPACE='Production/k0s' \
  --from-literal=PBS_ENCRYPTION_PASSWORD='<keyfile-passphrase>'
```

Add `PBS_FINGERPRINT` as needed.

## Manual run for validation

```bash
kubectl -n observability-production create job --from=cronjob/grafana-pbs-backup grafana-pbs-backup-manual-$(date +%s)
kubectl -n observability-production logs -l app.kubernetes.io/name=grafana-pbs-backup -c backup --tail=50 --follow
```

## Restore (manual, destructive)

There is no committed `grafana-pbs-restore-job.yaml` — Grafana is the only consumer of this DB and re-importable. To restore from PBS, run an out-of-band Job that:

1. `proxmox-backup-client restore` the `db.pxar` archive to a scratch dir.
2. `pg_restore --clean --if-exists --no-owner --no-acl -d grafana /restore/grafana.pgdump`.
3. Scale Grafana to 0 first to avoid concurrent writes during the restore (`kubectl -n observability-production scale deployment obs-kps-grafana --replicas=0`).

Use `clusters/production/apps/clutterstock/clutterstock-pbs-restore-job.yaml` as a template.

## Verify (without printing secret values)

```bash
kubectl -n observability-production describe secret grafana-pbs-backup
```
