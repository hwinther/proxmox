# Valkey (shared tiers) — optional authentication

Shared cache pods in **`shared-production`** and **`shared-test`** run **Valkey** with the Redis protocol on Service **`redis:6379`**. The GitOps manifests **do not** set `requirepass`, so clients that only supply host/port (for example `hwinther/test` `api.leaderboard` using `REDIS_HOST` / `REDIS_PORT`) keep working without code changes.

Isolation relies on **NetworkPolicy** (and **CiliumNetworkPolicy** where used) so only expected namespaces can reach port 6379.

## Optional: enable `requirepass`

If you turn on authentication on Valkey, you must:

1. **Server** — set a password (for example via `--requirepass` and an env var from a Secret) on the Valkey Deployment in the shared bundle.
2. **Authelia** — set `configMap.session.redis.password` in the Authelia HelmRelease: `disabled: false`, `secret_name`, and create the secret with key `session.redis.password.txt` (see [Authelia session Redis](https://www.authelia.com/configuration/session/redis/)).
3. **App frontends** — use a Redis URL that includes the password (`redis://:PASSWORD@redis.shared-….svc.cluster.local:6379`) or extend apps to pass `password` into `ioredis` (not supported by the current `test` leaderboard route without a code change).

Example Secret for Authelia (production namespace **`authelia-production`**), after you choose a long random password:

```bash
kubectl create secret generic authelia-session-valkey \
  --namespace authelia-production \
  --from-literal=session.redis.password.txt='REPLACE_WITH_LONG_RANDOM'
```

Then point the chart at `secret_name: authelia-session-valkey` and remove `password.disabled` (or set `disabled: false`).
