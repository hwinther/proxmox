# Cluster-wide PBS encryption keyfile

A single Secret **`pbs-encryption-keyfile`** in namespace **`platform-production`** holds the [Proxmox Backup Server AES-256-GCM keyfile](https://pbs.proxmox.com/docs/backup-client.html#encryption) used by every PBS backup/restore Job in this cluster. Kyverno (`clone-pbs-encryption-keyfile` ClusterPolicy) clones it into each consuming app namespace — Jobs reference the cloned Secret, never the source.

## Why one cluster-wide key

Per-Job keys scale poorly (one Secret per backup target → eventually wants an operator). Per-environment keys double the bookkeeping with little practical isolation in a single-operator homelab. One key keeps the off-cluster backup of the key material small and the rotation story simple.

If at some point this cluster gains real multi-tenancy or a second operator, split into per-environment or per-team keys then.

## Generate the keyfile (once)

On any host with `proxmox-backup-client` installed:

```bash
proxmox-backup-client key create /tmp/pbs-encryption.key
# Optionally password-protect it. If you do, set PBS_ENCRYPTION_PASSWORD in each
# consuming namespace's PBS-backup Secret (e.g. clutterstock-test-pbs-backup).
```

**Lose the keyfile, lose every encrypted PBS backup it produced.** The key never leaves the client — PBS stores opaque encrypted chunks. Back up the key material out-of-band (password manager, offline media), not just on the cluster it protects.

## Create the Secret

The Secret data key inside must be named `keyfile` — that's what each Job's volume mount expects (`items.key: keyfile`).

```bash
kubectl -n platform-production create secret generic pbs-encryption-keyfile \
  --from-file=keyfile=/tmp/pbs-encryption.key
shred -u /tmp/pbs-encryption.key
```

Once present, Kyverno clones it into the namespaces listed in `clone-pbs-encryption-keyfile`. Verify:

```bash
kubectl get secret pbs-encryption-keyfile -A
```

## Add a new consuming namespace

Append a rule to `kyverno-clusterpolicy-clone-pbs-encryption-keyfile.yaml`:

```yaml
- name: clone-to-<namespace>
  match:
    any:
    - resources:
        kinds: [Secret]
        namespaces: [platform-production]
        names: [pbs-encryption-keyfile]
  generate:
    apiVersion: v1
    kind: Secret
    name: pbs-encryption-keyfile
    namespace: <namespace>
    synchronize: true
    clone:
      namespace: platform-production
      name: pbs-encryption-keyfile
```

The consuming namespace also needs a Role binding granting Kyverno's admission and background controllers `secrets` write access (see e.g. `clutterstock-test/kyverno-rbac-generate-cluttertestdb-app-secret.yaml` — that role's rules already cover all secrets in the namespace despite the secret-specific name).

## Rotate the key

PBS encryption is symmetric — rotating means future backups use the new key, but past backups still need the old key to restore. Strategy options:
- **Append-only**: keep both old and new keyfiles in the source Secret under different data keys. Mount both and let restores pick the right one (would need Job changes to support multi-key).
- **Cutover**: replace the Secret in `platform-production`; Kyverno re-syncs to consumers; future backups encrypt with new key; restores from snapshots taken before the cutover need the archived old key.

For a homelab, cutover is usually fine — note the cutover date alongside the off-cluster key archive so you know which key restores which snapshots.
