# romslig secrets & prerequisites (`romslig-production`)

romslig's API and web frontend come from the signed manifest artifact in [`romslig-manifests.yaml`](romslig-manifests.yaml). Everything below is created by hand on the cluster (or in the external LDAP directory) — none of it is stored in git. Do not commit real values, and do not commit `Secret` manifests with placeholder values.

| What                 | Kind       | Namespace / place     | Required                                 |
| -------------------- | ---------- | --------------------- | ---------------------------------------- |
| `romslig-pg-secret`  | Secret     | `postgres-production` | yes                                      |
| `romslig-pbs-backup` | Secret     | `romslig-production`  | yes (daily backup CronJob)               |
| `romslig-anthropic`  | Secret     | `romslig-production`  | only for `AI_MODE: server`               |
| `romslig-users`      | LDAP group | external slapd        | yes (Authelia lets only members through) |

## `romslig-pg-secret` (namespace `postgres-production`)

CNPG managed role **`romslig`** owns the **`romslig`** database (`../postgres-production/database-romslig.yaml`) on cluster **`postgres-prod`**. The role password comes from this Secret (`managed.roles[].passwordSecret` in `../postgres-production/cluster-postgres-prod.yaml`), and Kyverno clones it into **`romslig-production`** (`../postgres-production/kyverno-generatingpolicy-clone-romslig-pg-secret.yaml`) for the API Deployment (`PG_SECRET`) and the PBS backup/restore Jobs. See [`../../../../docs/postgres-naming-convention.md`](../../../../docs/postgres-naming-convention.md).

```bash
kubectl create secret generic romslig-pg-secret \
  --from-literal=password=<password> \
  -n postgres-production
```

`password` is the only key consumed. Create the Secret **before** (or right after) Flux applies the new managed role; CNPG retries the role until the Secret exists. Check that the clone arrived:

```bash
kubectl -n romslig-production describe secret romslig-pg-secret
```

To rotate, update the source Secret in `postgres-production`; CNPG changes the role password and Kyverno re-syncs the clone. Restart the API afterwards so it reads the new value:

```bash
kubectl -n romslig-production rollout restart deployment romslig-api
```

## `romslig-pbs-backup` (namespace `romslig-production`)

The backup CronJob ([`romslig-pbs-backup-job.yaml`](romslig-pbs-backup-job.yaml)) and the manual restore Job ([`romslig-pbs-restore-job.yaml`](romslig-pbs-restore-job.yaml)) load their environment from this Secret. The cluster-wide PBS encryption keyfile lives in `platform-production` and is cloned here automatically (the namespace carries `pbs.wsh.no/encryption-keyfile: "true"`) — see [`../platform-production/pbs-encryption-keyfile.md`](../platform-production/pbs-encryption-keyfile.md).

### Required keys

| Key              | Purpose                                                                                                                                 |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `PBS_REPOSITORY` | Default repository string for `proxmox-backup-client` (user, host, port, datastore).                                                    |
| `PBS_PASSWORD`   | Password or API token secret value. See [Environment variables](https://pbs.proxmox.com/docs/backup-client.html#environment-variables). |

### Optional keys

| Key                       | When to set                                                                                                                                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PBS_FINGERPRINT`         | Self-signed PBS or pinned cert fingerprint.                                                                                                                                                             |
| `PBS_NAMESPACE`           | PBS datastore namespace (e.g. `Production/romslig`). Job appends `--ns $PBS_NAMESPACE` to backup and restore. Restores must use the same value as the backup. Create the namespace in the PBS UI first. |
| `PBS_ENCRYPTION_PASSWORD` | Only when the keyfile is password-protected. Read from env by `proxmox-backup-client`.                                                                                                                  |
| `PBS_RESTORE_SNAPSHOT`    | Only for **restore**: full snapshot path (e.g. `host/romslig-postgres/2026-11-10T03:45:00Z`).                                                                                                           |

### Create the Secret

```bash
kubectl -n romslig-production create secret generic romslig-pbs-backup \
  --from-literal=PBS_REPOSITORY='user@pbs!tokenid@pbs.example.com:8007:datastore' \
  --from-literal=PBS_PASSWORD='your-api-token-uuid-here' \
  --from-literal=PBS_NAMESPACE='Production/romslig'
```

Add `PBS_ENCRYPTION_PASSWORD` and/or `PBS_FINGERPRINT` literals as needed. To add or change a key later without touching the others:

```bash
kubectl -n romslig-production patch secret romslig-pbs-backup --type merge -p '{
  "stringData": {
    "PBS_ENCRYPTION_PASSWORD": "<keyfile-password>"
  }
}'
```

Set a value to `null` in the same patch to remove a key. Validate before the next scheduled run (03:45 Europe/Oslo) with an out-of-band Job:

```bash
kubectl -n romslig-production create job --from=cronjob/romslig-pbs-backup romslig-pbs-backup-manual-$(date +%s)
```

### Restore (manual, destructive)

The restore Job is intentionally **not** in `kustomization.yaml` so Flux doesn't re-run it on reconcile. Apply manually:

```bash
# 1. Set the snapshot path to restore from
kubectl -n romslig-production patch secret romslig-pbs-backup --type merge \
  -p '{"stringData":{"PBS_RESTORE_SNAPSHOT":"host/romslig-postgres/2026-11-10T03:45:00Z"}}'

# 2. Stop the API (writes during restore would conflict with --clean drops). Suspend the Flux
#    Kustomization first, or it scales the Deployment back up on its next reconcile.
flux -n romslig-production suspend kustomization romslig
kubectl -n romslig-production scale deployment romslig-api --replicas=0

# 3. Run the restore and watch it
kubectl apply -f clusters/production/apps/romslig/romslig-pbs-restore-job.yaml
kubectl -n romslig-production get job romslig-pbs-restore-v001 -w

# 4. Bring the API back (resume restores the artifact's replica count)
flux -n romslig-production resume kustomization romslig

# 5. Optional: clear PBS_RESTORE_SNAPSHOT so it's not stale next time
kubectl -n romslig-production patch secret romslig-pbs-backup --type merge \
  -p '{"stringData":{"PBS_RESTORE_SNAPSHOT":null}}'
```

`pg_restore --clean --if-exists --no-owner --no-acl` drops and recreates objects owned by the `romslig` role inside the database — verify on a clone first if there's any doubt.

## `romslig-anthropic` (optional, namespace `romslig-production`)

Production starts with **`AI_MODE: byok`**: each user supplies their own Anthropic API key in the app, and the cluster holds none. To have the API proxy to `api.anthropic.com` with a server-held key instead:

1. Create the Secret (key **`api-key`**):

   ```bash
   kubectl -n romslig-production create secret generic romslig-anthropic \
     --from-literal=api-key='<anthropic-api-key>'
   ```

2. In [`romslig-manifests.yaml`](romslig-manifests.yaml), set `AI_MODE: server` and `AI_SECRET: romslig-anthropic` under `postBuild.substitute`, and merge. Egress to the internet on 443 is already allowed for `romslig-api` (`networkpolicies.yaml`).

To rotate the key, replace the value and restart the API:

```bash
kubectl -n romslig-production patch secret romslig-anthropic --type merge \
  -p '{"stringData":{"api-key":"<new-anthropic-api-key>"}}'
kubectl -n romslig-production rollout restart deployment romslig-api
```

## LDAP group `romslig-users` (external slapd)

Authelia gates `romslig.wsh.no` with `two_factor` for members of **`romslig-users`** and denies everyone else (rules in [`../authelia-production/authelia-helmrelease.yaml`](../authelia-production/authelia-helmrelease.yaml)); the app also checks the group itself (`ALLOWED_GROUP`). The group lives in the external directory (`ldap://auth.oh.wsh.no`, base `dc=oh,dc=wsh,dc=no`), not in the cluster. Authelia's `groups_filter` accepts `groupOfUniqueNames`/`uniqueMember`, `groupOfNames`/`member` and `posixGroup`/`memberUid`; the example uses `groupOfUniqueNames` under `ou=Groups`, like `k8s-admins`.

1. Create the group with its first member (a `groupOfUniqueNames` needs at least one `uniqueMember`):

   ```bash
   ldapadd -H ldap://auth.oh.wsh.no -ZZ -x -D '<admin-bind-dn>' -W <<'EOF'
   dn: cn=romslig-users,ou=Groups,dc=oh,dc=wsh,dc=no
   objectClass: groupOfUniqueNames
   cn: romslig-users
   uniqueMember: uid=<username>,ou=People,dc=oh,dc=wsh,dc=no
   EOF
   ```

2. Add more users:

   ```bash
   ldapmodify -H ldap://auth.oh.wsh.no -ZZ -x -D '<admin-bind-dn>' -W <<'EOF'
   dn: cn=romslig-users,ou=Groups,dc=oh,dc=wsh,dc=no
   changetype: modify
   add: uniqueMember
   uniqueMember: uid=<other-username>,ou=People,dc=oh,dc=wsh,dc=no
   EOF
   ```

3. Check what Authelia will see (the `uniqueMember` value must be the user's real DN):

   ```bash
   ldapsearch -H ldap://auth.oh.wsh.no -ZZ -x -D '<admin-bind-dn>' -W \
     -b 'ou=Groups,dc=oh,dc=wsh,dc=no' '(cn=romslig-users)' uniqueMember
   ```

Authelia re-reads LDAP group membership for active sessions periodically (`authentication_backend.refresh_interval`, default 5 minutes), so additions and removals take effect without a re-login after a short delay.

## Verify (without printing secret values)

```bash
kubectl -n postgres-production describe secret romslig-pg-secret
kubectl -n romslig-production describe secret romslig-pg-secret romslig-pbs-backup
```

`describe` lists each data key and byte size, not the decoded values.
