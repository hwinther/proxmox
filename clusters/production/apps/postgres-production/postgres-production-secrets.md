# Secrets — `postgres-production`

See [`../../docs/postgres-naming-convention.md`](../../../docs/postgres-naming-convention.md) for the full naming convention.

## clutterstock

CNPG managed role **`clutterstock`** (target state; currently still `app`) owns the **`clutterstock`** database on cluster **`postgres-prod`**.

Secret **`clutterstock-pg-secret`** (target; currently `postgres-prod-app`) is created manually and cloned by Kyverno into **`clutterstock-production`**.

Inspect the connection URI:

```bash
kubectl get secret clutterstock-pg-secret -n postgres-production -o jsonpath='{.data.uri}' | base64 -d
echo
```

## authelia

CNPG managed role **`authelia`** owns the **`authelia`** database on cluster **`postgres-prod`**.

Secret **`authelia-pg-secret`** holds the role password and is referenced in `managed.roles[].passwordSecret` in `cluster-postgres-prod.yaml`. Authelia itself reads the password from the separate **`authelia-storage`** secret — see [`../authelia-production/authelia-storage-secrets.md`](../authelia-production/authelia-storage-secrets.md).

```bash
kubectl create secret generic authelia-pg-secret \
  --from-literal=password=<password> \
  -n postgres-production
```

## Adminer + OIDC

**oauth2-proxy** in front of Adminer; Authelia OIDC public client **`adminer-pg-prod`** (PKCE, `two_factor`) in [`../authelia-production/authelia-helmrelease.yaml`](../authelia-production/authelia-helmrelease.yaml). Ingress **`https://adminer-pg-prod.mgmt.wsh.no`**. Default server **`postgres-prod-rw.postgres-production.svc.cluster.local`**.

### Secret `oauth2-proxy-adminer` (namespace `postgres-production`)

Use a **`cookie-secret`** that oauth2-proxy accepts (16 / 24 / 32 bytes after its decode step). Avoid bare `openssl rand -base64 32`: if the value contains **`+` or `/`**, decoding fails and the proxy sees a 44-byte raw string and crashes. Prefer:

```bash
kubectl create secret generic oauth2-proxy-adminer \
  --namespace postgres-production \
  --from-literal=cookie-secret="$(openssl rand -hex 16)"
```
