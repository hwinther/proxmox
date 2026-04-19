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

## Adminer

Ingress **`https://adminer-pg-prod.mgmt.wsh.no`** (Authelia). Default server **`clutterstockdb-rw.postgres-production.svc.cluster.local`**; you can enter other `-rw` hosts in the UI if you add more clusters later. Listed on Homepage via **`gethomepage.dev/*`** Ingress annotations (cluster mode **`ingress: true`**).
