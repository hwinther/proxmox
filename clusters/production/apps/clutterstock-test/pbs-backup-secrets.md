# Proxmox Backup Server credentials (`clutterstock-test`)

The backup and restore Jobs load environment variables from the Kubernetes Secret **`clutterstock-test-pbs-backup`** in namespace **`clutterstock-test`**. Create and update it with `kubectl` (or SealedSecrets / External Secrets / your usual secret workflow). Do not commit real values to git.

## Required keys

| Key              | Purpose                                                                                                                                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PBS_REPOSITORY` | Default repository string for `proxmox-backup-client` (user, host, port, datastore). Format: [Backup repository locations](https://pbs.proxmox.com/docs/backup-client.html#backup-repository-locations). |
| `PBS_PASSWORD`   | Password or API token secret value. See [Environment variables](https://pbs.proxmox.com/docs/backup-client.html#environment-variables).                                                                  |

## Optional keys

| Key                    | When to set                                                                                                                                                                                                     |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PBS_FINGERPRINT`      | If PBS uses a self-signed certificate or you pin the server cert fingerprint. Same PBS docs section as above.                                                                                                   |
| `PBS_RESTORE_SNAPSHOT` | Only for **restore**: full snapshot path (e.g. `host/clutterstock-test-postgres/2025-04-13T10:00:00Z`). Omit for backup-only. You can add it temporarily, run the restore Job, then remove it or leave it unused. |

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

## Add or change `PBS_RESTORE_SNAPSHOT` for a restore

**Option A — patch (merge):**

```bash
kubectl -n clutterstock-test patch secret clutterstock-test-pbs-backup \
  --type merge \
  -p '{"stringData":{"PBS_RESTORE_SNAPSHOT":"host/clutterstock-test-postgres/2025-04-13T10:00:00Z"}}'
```

**Option B — recreate** with all literals (include every key you still need):

```bash
kubectl -n clutterstock-test delete secret clutterstock-test-pbs-backup
kubectl -n clutterstock-test create secret generic clutterstock-test-pbs-backup \
  --from-literal=PBS_REPOSITORY='...' \
  --from-literal=PBS_PASSWORD='...' \
  --from-literal=PBS_RESTORE_SNAPSHOT='host/clutterstock-test-postgres/2025-04-13T10:00:00Z'
```

## Verify (without printing secret values)

```bash
kubectl -n clutterstock-test describe secret clutterstock-test-pbs-backup
```

`describe` lists each data key and byte size, not the decoded values.
