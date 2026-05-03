# Proxmox Backup Server credentials (`authelia-production`)

The backup and restore Jobs load environment variables from the Kubernetes Secret **`authelia-pbs-backup`** in namespace **`authelia-production`**. Create and update it with `kubectl` (or SealedSecrets / External Secrets / your usual secret workflow). Do not commit real values to git.

The cluster-wide PBS encryption keyfile lives in `platform-production` and is cloned here automatically — see [`../platform-production/pbs-encryption-keyfile.md`](../platform-production/pbs-encryption-keyfile.md).

## Required keys

| Key              | Purpose                                                                                                                                 |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `PBS_REPOSITORY` | Default repository string for `proxmox-backup-client` (user, host, port, datastore).                                                    |
| `PBS_PASSWORD`   | Password or API token secret value. See [Environment variables](https://pbs.proxmox.com/docs/backup-client.html#environment-variables). |

## Optional keys

| Key                       | When to set                                                                                                                                                                                                |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PBS_FINGERPRINT`         | Self-signed PBS or pinned cert fingerprint.                                                                                                                                                                |
| `PBS_NAMESPACE`           | PBS datastore namespace (e.g. `Production/authelia`). Job appends `--ns $PBS_NAMESPACE` to backup and restore. Restores must use the same value as the backup. Create the namespace in the PBS UI first.  |
| `PBS_ENCRYPTION_PASSWORD` | Only when the keyfile is password-protected.                                                                                                                                                               |
| `PBS_RESTORE_SNAPSHOT`    | Only for **restore**: full snapshot path (e.g. `host/authelia-postgres/2026-05-04T03:00:00Z`).                                                                                                             |

## Create the Secret

```bash
kubectl -n authelia-production create secret generic authelia-pbs-backup \
  --from-literal=PBS_REPOSITORY='user@pbs!tokenid@pbs.example.com:8007:datastore' \
  --from-literal=PBS_PASSWORD='your-api-token-uuid-here' \
  --from-literal=PBS_NAMESPACE='Production/authelia'
```

## Add or change an optional key

**Patch (merge), keeping existing keys untouched:**

```bash
kubectl -n authelia-production patch secret authelia-pbs-backup --type merge -p '{
  "stringData": {
    "PBS_NAMESPACE": "Production/authelia",
    "PBS_ENCRYPTION_PASSWORD": "<keyfile-password>"
  }
}'
```

Set a value to `null` in the same patch to remove a key. Then bump or delete the Job to roll a fresh pod (env from a Secret is not re-read by a running pod).

## Restore (manual, destructive)

The restore Job is intentionally **not** in `kustomization.yaml`.

```bash
# 1. Set the snapshot path to restore from
kubectl -n authelia-production patch secret authelia-pbs-backup --type merge \
  -p '{"stringData":{"PBS_RESTORE_SNAPSHOT":"host/authelia-postgres/2026-05-04T03:00:00Z"}}'

# 2. Stop Authelia (active sessions/consent writes would conflict with --clean)
kubectl -n authelia-production scale deployment authelia --replicas=0

# 3. Run the restore
kubectl apply -f clusters/production/apps/authelia-production/authelia-pbs-restore-job.yaml

# 4. Bring Authelia back up
kubectl -n authelia-production scale deployment authelia --replicas=1
```

**Critical**: the `storage.encryption.key` in the `authelia-storage` Secret must match the key in use at the time of the backup. Restoring a snapshot taken under a different encryption key leaves rows that Authelia can decrypt only with the original key — see [`authelia-storage-secrets.md`](authelia-storage-secrets.md).

## Verify (without printing secret values)

```bash
kubectl -n authelia-production describe secret authelia-pbs-backup
```
