# CloudNative-PG credentials (`postgres-test`)

Passwords and connection strings are **not** stored in Git. This namespace holds **`Cluster`** resources for the **test tier**: **`testdb`** (sample `test-api`) and **`cluttertestdb`** (Clutterstock test). Production-tier Clutterstock Postgres lives in **`postgres-production`** — see [`../postgres-production/postgres-production-secrets.md`](../postgres-production/postgres-production-secrets.md).

## `testdb` (sample test API)

CloudNative-PG creates **`testdb-app`** in namespace **`postgres-test`**. It is typed **`kubernetes.io/basic-auth`** and includes connection material (for example **`uri`**, **`username`**, **`password`**, **`host`**, **`port`**, **`dbname`**) suitable for application clients.

Read-only inspection:

```bash
kubectl get secret testdb-app -n postgres-test -o jsonpath='{.data.uri}' | base64 -d
echo
```

## Copy in `test-test` for `secretKeyRef`

Kubernetes does not allow a Pod in **`test-test`** to mount a Secret in **`postgres-test`**. This repo uses a **Kyverno** `ClusterPolicy` (**`clone-testdb-app-secret-to-test-test`**) to keep a synchronized copy of **`testdb-app`** in **`test-test`**, so **`test-api`** can use `secretKeyRef` on **`testdb-app`** in its own namespace.

If the clone has not run yet (policy or Kyverno timing), **`test-api`** may fail to start until the Secret appears in **`test-test`**. After the source Secret exists:

```bash
kubectl get secret testdb-app -n test-test -o yaml
```

To **clone manually** (e.g. without Kyverno), after `testdb-app` exists in `postgres-test`:

```bash
kubectl get secret testdb-app -n postgres-test -o yaml \
  | yq 'del(.metadata.uid, .metadata.resourceVersion, .metadata.creationTimestamp, .metadata.namespace, .metadata.ownerReferences)' \
  | yq '.metadata.namespace = "test-test"' \
  | kubectl apply -f -
```

(Use **`yq`** or edit by hand; strip controller-owned metadata before `apply`.)

## Optional: fixed application password (`bootstrap.initdb.secret`)

To set the application owner password from a Secret you create (instead of a fully operator-generated password), add **`spec.bootstrap.initdb.secret.name`** on the `Cluster` and create a **`kubernetes.io/basic-auth`** Secret in **`postgres-test`** whose **`username`** matches **`spec.bootstrap.initdb.owner`**. See CloudNative-PG bootstrap docs. When you use this path, confirm whether the operator still materializes **`testdb-app`** the same way for your chart/operator version.

## `cluttertestdb` (Clutterstock test API)

Operator Secret **`cluttertestdb-app`** in **`postgres-test`** (database **`clutterstock`**, owner **`app`**). Kyverno policy **`clone-cluttertestdb-app-secret-to-clutterstock-test`** syncs it into **`clutterstock-test`** so **`clutterstock-api`** can use **`ConnectionStrings__ClutterStockPostgres`** via `secretKeyRef` (SQLite **`ConnectionStrings__ClutterStock`** stays until the app switches).

```bash
kubectl get secret cluttertestdb-app -n clutterstock-test -o jsonpath='{.data.uri}' | base64 -d
echo
```

## Adminer (test tier) + OIDC

Traffic: **browser → Traefik → `oauth2-proxy-adminer` → Adminer**. OIDC uses Authelia **`https://auth.wsh.no`** with public clients **`adminer-pg-test`** (PKCE, `two_factor`), defined in [`../authelia-production/authelia-helmrelease.yaml`](../authelia-production/authelia-helmrelease.yaml). Vanilla Adminer has no OIDC; **oauth2-proxy** performs the code flow then proxies to Adminer.

### Secret `oauth2-proxy-adminer` (namespace `postgres-test`)

Create **before** the oauth2-proxy Deployment rolls (key **`cookie-secret`** must end up as **16, 24, or 32 bytes** after oauth2-proxy’s parsing). Do **not** use `openssl rand -base64 32` alone: values containing **`+` or `/`** fail RawURL base64 decoding, so the proxy treats the whole string as raw bytes (**44** characters) and exits with `cookie_secret must be 16, 24, or 32 bytes`. Prefer a **32-character hex** string (16 random bytes):

```bash
kubectl create secret generic oauth2-proxy-adminer \
  --namespace postgres-test \
  --from-literal=cookie-secret="$(openssl rand -hex 16)"
```

Ingress **`https://adminer-pg-test.mgmt.wsh.no`**. Default DB server in Adminer remains **`testdb-rw.postgres-test.svc.cluster.local`**; use **`cluttertestdb-rw.postgres-test.svc.cluster.local`** for Clutterstock test. Homepage discovers the Ingress via **`gethomepage.dev/*`** when cluster **`ingress: true`**.

## Superuser

Superuser access over the network stays **disabled** unless you explicitly enable it on the `Cluster`; prefer the **`-app`** credentials for applications.

## Test-deployment cluster (`clusters/test-deployment`)

The separate Flux root under **`clusters/test-deployment`** installs the same operator chart and a **`Cluster`** named **`testdb`** in namespace **`test`** (same namespace as **`test-api`**), using storage class **`local-path`**. The operator still creates **`testdb-app`** in **`test`**, so no Kyverno clone is required there. See [`../../../test-deployment/apps/cnpg-test/cluster.yaml`](../../../test-deployment/apps/cnpg-test/cluster.yaml).
