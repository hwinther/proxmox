# CloudNative-PG credentials (`postgres-production` / `clutterstockdb`)

Same pattern as [`../postgres-test/postgres-test-secrets.md`](../postgres-test/postgres-test-secrets.md): the operator creates **`clutterstockdb-app`** in **`postgres-production`**, and Kyverno clones it to **`clutterstock-production`** as **`clutterstockdb-app`** for `secretKeyRef`.

Inspect the source URI:

```bash
kubectl get secret clutterstockdb-app -n postgres-production -o jsonpath='{.data.uri}' | base64 -d
echo
```

Confirm the copy in the app namespace:

```bash
kubectl get secret clutterstockdb-app -n clutterstock-production -o yaml
```

The API Deployment reads **`ConnectionStrings__ClutterStockPostgres`** from key **`uri`** until you switch the app off SQLite (`ConnectionStrings__ClutterStock`).

## Adminer + OIDC

**oauth2-proxy** in front of Adminer; Authelia OIDC public client **`adminer-pg-prod`** (PKCE, `two_factor`) in [`../authelia-production/authelia-helmrelease.yaml`](../authelia-production/authelia-helmrelease.yaml). Ingress **`https://adminer-pg-prod.mgmt.wsh.no`**. Default server **`clutterstockdb-rw.postgres-production.svc.cluster.local`**.

### Secret `oauth2-proxy-adminer` (namespace `postgres-production`)

Use a **`cookie-secret`** that oauth2-proxy accepts (16 / 24 / 32 bytes after its decode step). Avoid bare `openssl rand -base64 32`: if the value contains **`+` or `/`**, decoding fails and the proxy sees a **44-byte** raw string and crashes. Prefer:

```bash
kubectl create secret generic oauth2-proxy-adminer \
  --namespace postgres-production \
  --from-literal=cookie-secret="$(openssl rand -hex 16)"
```

Homepage: **`gethomepage.dev/*`** on the Ingress with cluster **`ingress: true`**.
