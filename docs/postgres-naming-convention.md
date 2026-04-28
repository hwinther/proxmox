# PostgreSQL Naming Convention

Conventions for CNPG clusters, databases, roles, and secrets across all environments.

## Clusters

One shared cluster per environment, named `postgres-<env>`, deployed in the `postgres-<env>onment` namespace.

| Environment | Cluster name    | Namespace             |
| ----------- | --------------- | --------------------- |
| Production  | `postgres-prod` | `postgres-production` |
| Test        | `postgres-test` | `postgres-test`       |

The cluster file is `cluster-postgres-<env>.yaml`.

## Databases

One logical database per application, named after the application.

| App          | Database name  |
| ------------ | -------------- |
| clutterstock | `clutterstock` |
| authelia     | `authelia`     |
| test-api     | `test-api`     |

Each database is declared as a CNPG `Database` resource in the cluster namespace, in a file named `database-<appname>.yaml`.

## PostgreSQL roles

One dedicated role per application, named after the application. No application shares the `app` bootstrap role — that role is unused after initial cluster creation.

| App          | Role name      |
| ------------ | -------------- |
| clutterstock | `clutterstock` |
| authelia     | `authelia`     |
| test-api     | `test-api`     |

Roles are declared in the `Cluster` spec under `managed.roles` with `login: true` and a `passwordSecret` reference.

## Secrets

### Application secret (in the cluster namespace)

Named `<appname>-pg-secret`. Contains the PostgreSQL password for the application role. Created manually and referenced in `managed.roles[].passwordSecret`.

```
kubectl create secret generic <appname>-pg-secret \
  --from-literal=password=<password> \
  -n postgres-<env>onment
```

### Application secret (in the app namespace)

The same secret name `<appname>-pg-secret` is cloned by Kyverno into the application's namespace so the deployment can reference it via `secretKeyRef`.

The Kyverno `ClusterPolicy` file is named `kyverno-clusterpolicy-clone-<appname>-pg-secret.yaml` and lives in the cluster namespace app directory. The supporting RBAC is in `kyverno-rbac-generate-<appname>-pg-secret.yaml` in the application's app directory.

### CNPG-managed secrets (do not reference directly)

CNPG auto-generates `<cluster>-app`, `<cluster>-superuser`, `<cluster>-ca`, `<cluster>-replication`, and `<cluster>-server` secrets. These are internal to the cluster operator and not used by applications.

## Current state vs. target

| App                 | Cluster         | Role (current → target) | Secret (current → target)                      |
| ------------------- | --------------- | ----------------------- | ---------------------------------------------- |
| clutterstock (prod) | `postgres-prod` | `app` → `clutterstock`  | `postgres-prod-app` → `clutterstock-pg-secret` |
| authelia            | `postgres-prod` | `authelia` ✓            | `authelia-pg-user` → `authelia-pg-secret`      |
| clutterstock (test) | `postgres-test` | `app` → `clutterstock`  | `cluttertestdb-app` → `clutterstock-pg-secret` |
| test-api            | `postgres-test` | `app` → `test-api`      | `testdb-app` → `test-api-pg-secret`            |

## Summary of files per app

For each application using postgres, there should be:

**In `postgres-<env>onment/`:**
- `database-<appname>.yaml` — CNPG `Database` resource
- `kyverno-clusterpolicy-clone-<appname>-pg-secret.yaml` — clones the secret into the app namespace

**In the application's app directory:**
- `kyverno-rbac-generate-<appname>-pg-secret.yaml` — RBAC for Kyverno to write secrets in the app namespace
