# Proxmox Backup Server credentials (`clutterstock-test`)

The backup and restore Jobs load environment variables from the Kubernetes Secret **`clutterstock-test-pbs-backup`** in namespace **`clutterstock-test`**. Create and update it with `kubectl` (or SealedSecrets / External Secrets / your usual secret workflow). Do not commit real values to git.

## Required keys

| Key              | Purpose                                                                                                                                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PBS_REPOSITORY` | Default repository string for `proxmox-backup-client` (user, host, port, datastore). Format: [Backup repository locations](https://pbs.proxmox.com/docs/backup-client.html#backup-repository-locations). |
| `PBS_PASSWORD`   | Password or API token secret value. See [Environment variables](https://pbs.proxmox.com/docs/backup-client.html#environment-variables).                                                                  |

## Optional keys

| Key                       | When to set                                                                                                                                                                                                       |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PBS_FINGERPRINT`         | If PBS uses a self-signed certificate or you pin the server cert fingerprint. Same PBS docs section as above.                                                                                                     |
| `PBS_NAMESPACE`           | PBS datastore namespace (e.g. `Production/clutterstock-test`). Job appends `--ns $PBS_NAMESPACE` to both backup and restore. Restores must use the same value as the backup. Create the namespace in the PBS UI.  |
| `PBS_ENCRYPTION_PASSWORD` | Only when the keyfile is password-protected (see `clutterstock-test-pbs-keyfile` Secret below). Read from env by `proxmox-backup-client`.                                                                         |
| `PBS_RESTORE_SNAPSHOT`    | Only for **restore**: full snapshot path (e.g. `host/clutterstock-test-postgres/2025-04-13T10:00:00Z`). Omit for backup-only. You can add it temporarily, run the restore Job, then remove it or leave it unused. |

## Create the Secret (CLI)

Replace placeholders with your PBS user, token, host, datastore, and optional fingerprint.

```bash
kubectl -n clutterstock-test create secret generic clutterstock-test-pbs-backup \
  --from-literal=PBS_REPOSITORY='user@pbs!tokenid@pbs.example.com:8007:datastore' \
  --from-literal=PBS_PASSWORD='your-api-token-uuid-here'
```

With optional fingerprint:

```bash
kubectl -n clutterstock-test create secret generic clutterstock-test-pbs-backup \
  --from-literal=PBS_REPOSITORY='user@pbs!tokenid@pbs.example.com:8007:datastore' \
  --from-literal=PBS_PASSWORD='your-api-token-uuid-here' \
  --from-literal=PBS_FINGERPRINT='aa:bb:cc:...'
```

If the Secret already exists, delete it first or use `kubectl apply` with a local manifest you generate yourself (still avoid committing secrets).

## Add or change an optional key (`PBS_NAMESPACE`, `PBS_ENCRYPTION_PASSWORD`, `PBS_RESTORE_SNAPSHOT`, `PBS_FINGERPRINT`)

**Option A — patch (merge), keeping existing keys untouched:**

```bash
kubectl -n clutterstock-test patch secret clutterstock-test-pbs-backup --type merge -p '{
  "stringData": {
    "PBS_NAMESPACE": "Production/clutterstock-test",
    "PBS_ENCRYPTION_PASSWORD": "<keyfile-password>"
  }
}'
```

Same shape for `PBS_RESTORE_SNAPSHOT` (e.g. `host/clutterstock-test-postgres/2025-04-13T10:00:00Z`) before running the restore Job, and for `PBS_FINGERPRINT`. To remove a key, set its value to `null` in the same patch.

**Option B — recreate** with all literals (include every key you still need; anything omitted is dropped):

```bash
kubectl -n clutterstock-test delete secret clutterstock-test-pbs-backup
kubectl -n clutterstock-test create secret generic clutterstock-test-pbs-backup \
  --from-literal=PBS_REPOSITORY='...' \
  --from-literal=PBS_PASSWORD='...' \
  --from-literal=PBS_NAMESPACE='Production/clutterstock-test' \
  --from-literal=PBS_ENCRYPTION_PASSWORD='<keyfile-password>'
```

After patching, the next scheduled CronJob run picks up the new env automatically — env from a Secret is read at pod start, so already-running pods are not affected. To validate the change before the next scheduled run, trigger an out-of-band Job from the CronJob:

```bash
kubectl -n clutterstock-test create job --from=cronjob/clutterstock-test-pbs-backup clutterstock-test-pbs-backup-manual-$(date +%s)
```

## Verify (without printing secret values)

```bash
kubectl -n clutterstock-test describe secret clutterstock-test-pbs-backup
```

`describe` lists each data key and byte size, not the decoded values.

## Client-side encryption keyfile

The PBS encryption keyfile is **not** namespace-local. A single cluster-wide Secret `pbs-encryption-keyfile` in `platform-production` is cloned here by Kyverno and mounted at `/etc/pbs/keyfile` by both Jobs — `--keyfile` is appended only when the file is present, so backups run unencrypted until the source Secret exists.

See [`../platform-production/pbs-encryption-keyfile.md`](../platform-production/pbs-encryption-keyfile.md) for how to generate the keyfile, create the source Secret, and rotate.

If the keyfile is password-protected, set `PBS_ENCRYPTION_PASSWORD` in this namespace's `clutterstock-test-pbs-backup` Secret (env-only — it is read by `proxmox-backup-client` from the environment).
