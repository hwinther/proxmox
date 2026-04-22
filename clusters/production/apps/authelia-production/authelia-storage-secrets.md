# Authelia storage (PostgreSQL on CNPG `clutterstockdb`)

Authelia uses **PostgreSQL** for persistence (OIDC consent, TOTP devices, etc.) on database **`authelia`**, role **`authelia`**, service **`clutterstockdb-rw.postgres-production.svc.cluster.local:5432`**. Declarative objects: [`../postgres-production/cluster-clutterstockdb.yaml`](../postgres-production/cluster-clutterstockdb.yaml) (`managed.roles`), [`../postgres-production/database-authelia.yaml`](../postgres-production/database-authelia.yaml).

## 1. CNPG role password (`postgres-production`)

Create **before** or as soon as you enable `managed.roles` (the operator reads this Secret):

```bash
kubectl create secret generic authelia-pg-user \
  --namespace postgres-production \
  --type kubernetes.io/basic-auth \
  --from-literal=username=authelia \
  --from-literal=password="$(openssl rand -base64 32)"
```

To rotate: update the Secret data; CNPG reconciles the role password.

## 2. Authelia encryption key + DB password (`authelia-production`)

The Helm chart mounts Secret **`authelia-storage`** with:

- **`storage.encryption.key`** — long random string (minimum 20 characters; 64+ random bytes recommended). **If you already ran Authelia with SQLite and need to keep data, reuse the same key** from the previous Secret or pod filesystem.
- **`storage.postgres.password.txt`** — **plaintext file body**: the **same** password as in `authelia-pg-user` (key `password`), with no extra newline if possible.

Example:

```bash
PG_PASS="$(kubectl get secret authelia-pg-user -n postgres-production -o jsonpath='{.data.password}' | base64 -d)"
kubectl create secret generic authelia-storage \
  --namespace authelia-production \
  --from-literal=storage.encryption.key="$(openssl rand -hex 32)" \
  --from-literal=storage.postgres.password.txt="$PG_PASS"
```

## 3. Apply order

1. `authelia-pg-user` in `postgres-production`
2. Flux applies Cluster (`managed.roles`) + `Database/authelia`
3. `authelia-storage` in `authelia-production`
4. Flux upgrades Authelia HelmRelease

If Authelia starts before the database exists, wait until the `Database` status is applied, then restart the Authelia Deployment.

## 4. Migrating from SQLite (`emptyDir`)

If you must keep existing Authelia data: take a backup with the project’s storage migration tooling and the **same** `storage.encryption.key`, or run the official migration procedure for your Authelia version. A fresh PostgreSQL database with a **new** encryption key starts empty (new device registrations, OIDC consents, etc.).
