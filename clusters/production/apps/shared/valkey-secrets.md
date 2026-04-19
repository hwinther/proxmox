# Valkey authentication (`requirepass`)

Shared Valkey runs with **`requirepass`**. Passwords live only in **Kubernetes Secrets** (not in this repo).

The in-cluster DNS name stays **`redis.<namespace>.svc.cluster.local:6379`** — the Deployment and Service keep the name **`redis`** so existing URLs and chart values do not need renames; only the container image is Valkey.

## 1. Create secrets (before Flux rolls the Valkey Deployment)

Use one long random password for each tier (**production** vs **test** can differ). Example (`openssl` on a workstation). Strip **newlines** plus base64’s **`+` and `/`** so the same string embeds cleanly in a `redis://…` URL without URL-encoding:

```bash
PW_PROD="$(openssl rand -base64 48 | tr -d '\n+/')"

kubectl create secret generic valkey-auth \
  --namespace shared-production \
  --from-literal=password="$PW_PROD"

kubectl create secret generic authelia-session-valkey \
  --namespace authelia-production \
  --from-literal=session.redis.password.txt="$PW_PROD"
```

**Test tier** (`shared-test`): same pattern with a separate password and namespace `shared-test` (no Authelia secret unless you add a consumer that needs it).

```bash
PW_TEST="$(openssl rand -base64 48 | tr -d '\n+/')"

kubectl create secret generic valkey-auth \
  --namespace shared-test \
  --from-literal=password="$PW_TEST"
```

**Test frontend** (`test-test` namespace) reads **`REDIS_URL`** from Secret **`test-frontend-valkey`** / key **`redis-url`**. Create it with the **same** password as `shared-test/valkey-auth`. If the password can contain URL-reserved characters, generate it with `tr -d '\n+/'` as above, or URL-encode it when building `redis-url`.

```bash
# After valkey-auth exists in shared-test with password PW_TEST:
kubectl create secret generic test-frontend-valkey \
  --namespace test-test \
  --from-literal=redis-url="redis://:${PW_TEST}@redis.shared-test.svc.cluster.local:6379/0"
```

RedisInsight in each shared namespace reads **`valkey-auth`** / key **`password`** via `RI_REDIS_PASSWORD` (see [Redis Insight preconfigure connections](https://redis.io/docs/latest/operate/redisinsight/install/install-on-docker/)).

### RedisInsight: `Cannot GET /api/databases/0/connect` (404)

Git manifests are the same for **prod** and **test**; this is almost always **state**, not a missing Ingress rule.

1. **Browser cache / local app data for that host** — RedisInsight keeps connection UI state in the browser. For **`redis-test.mgmt.wsh.no`**, do a **hard refresh**, **private window**, or clear **site data** for that origin, then open the UI again. (Prod can “work” while test fails if only test’s origin has stale DB id `0`.)
2. **Wrong `valkey-auth` in `shared-test`** — If `RI_REDIS_PASSWORD` does not match Valkey’s `requirepass`, pre-registration can fail and the server-side DB list may not match what the UI requests → **404** on connect. Re-check the Secret in **`shared-test`** (not only `test-test`).
3. **Startup order** — The RedisInsight Deployment includes an **init container** that loops until `valkey-cli … ping` succeeds against **`redis:6379`** with the same password, so the main container starts only after Valkey accepts AUTH.

If it still fails, check RedisInsight pod logs: `kubectl logs -n shared-test deploy/redisinsight -c redisinsight --tail=100`.

## 2. Authelia

The HelmRelease mounts **`authelia-session-valkey`** with key **`session.redis.password.txt`** and sets `configMap.session.redis.password.secret_name` to that Secret. The file content must match **`requirepass`** on Valkey in `shared-production`.

## 3. Application clients (your updates)

**Full `REDIS_URL`** (works with most Redis clients). Prefer passwords generated with `tr -d '\n+/'` as above; otherwise URL-encode reserved characters in the password:

```text
redis://:PASSWORD@redis.shared-production.svc.cluster.local:6379/0
```

Use logical DB **`0`** for app cache unless you intentionally share another DB index. Authelia uses **DB 15** via its own config (same password, different `SELECT`).

**Alternative:** keep `REDIS_HOST` / `REDIS_PORT` and add a **`REDIS_PASSWORD`** (or app-specific) env from a Secret — `ioredis` accepts `password` in the constructor options.

**Per-namespace Secrets:** client workloads cannot mount `shared-production/valkey-auth`; give each namespace its own Secret (e.g. `clutterstock-valkey` with key `redis-url` or `password`) created from the same `$PW_PROD`.

## 4. Rollout order

1. Create **`valkey-auth`** (and **`authelia-session-valkey`** if using Authelia) in the right namespaces.
2. Let Flux apply updated Deployments / HelmRelease. Until **`valkey-auth`** exists, the Valkey pod will stay in **`CreateContainerConfigError`**.

## Optional: rotation

Create a new Secret version (or new name), update references, rollout Valkey then clients (or overlap with dual-read if you design for it — not covered here).
