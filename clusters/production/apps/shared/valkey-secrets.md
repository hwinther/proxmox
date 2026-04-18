# Valkey authentication (`requirepass`)

Shared Valkey runs with **`requirepass`**. Passwords live only in **Kubernetes Secrets** (not in this repo).

The in-cluster DNS name stays **`redis.<namespace>.svc.cluster.local:6379`** — the Deployment and Service keep the name **`redis`** so existing URLs and chart values do not need renames; only the container image is Valkey.

## 1. Create secrets (before Flux rolls the Valkey Deployment)

Use one long random password for each tier (**production** vs **test** can differ). Example (`openssl` on a workstation):

```bash
PW_PROD="$(openssl rand -base64 48 | tr -d '\n')"

kubectl create secret generic valkey-auth \
  --namespace shared-production \
  --from-literal=password="$PW_PROD"

kubectl create secret generic authelia-session-valkey \
  --namespace authelia-production \
  --from-literal=session.redis.password.txt="$PW_PROD"
```

**Test tier** (`shared-test`): same pattern with a separate password and namespace `shared-test` (no Authelia secret unless you add a consumer that needs it).

```bash
PW_TEST="$(openssl rand -base64 48 | tr -d '\n')"

kubectl create secret generic valkey-auth \
  --namespace shared-test \
  --from-literal=password="$PW_TEST"
```

RedisInsight in each shared namespace reads **`valkey-auth`** / key **`password`** via `RI_REDIS_PASSWORD` (see [Redis Insight preconfigure connections](https://redis.io/docs/latest/operate/redisinsight/install/install-on-docker/)).

## 2. Authelia

The HelmRelease mounts **`authelia-session-valkey`** with key **`session.redis.password.txt`** and sets `configMap.session.redis.password.secret_name` to that Secret. The file content must match **`requirepass`** on Valkey in `shared-production`.

## 3. Application clients (your updates)

**Full `REDIS_URL`** (works with most Redis clients; URL-encode special characters in the password if needed):

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
