# Environment-scoped shared workloads (production cluster)

**Valkey** (Redis protocol) is **shared by multiple apps** on the same **environment line**, not duplicated per product namespace. The ClusterIP Service remains named **`redis`** on port **6379** so existing `redis://` URLs keep working.

| Bundle                       | Namespace               | Consumers (examples)                                                                                                                           |
| ---------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| [`production/`](production/) | **`shared-production`** | Prod-tier apps (`clutterstock-production`, …), **Authelia** sessions (logical DB **15**); RedisInsight UI **`https://redis-prod.mgmt.wsh.no`** |
| [`test/`](test/)             | **`shared-test`**       | Test-tier apps (`test-test`, …); RedisInsight UI **`https://redis-test.mgmt.wsh.no`**                                                          |

Each tier uses a **persistent volume** (`valkey-data`, `ceph-rbd`) with **AOF** (`--appendonly yes`). Apps point **`REDIS_URL`** at `redis://redis.<namespace>.svc.cluster.local:6379` (default logical DB **0**).

Optional `requirepass` and client Secret wiring are documented in [`valkey-secrets.md`](valkey-secrets.md) (not enabled in GitOps so `REDIS_HOST` / `REDIS_PORT` clients stay passwordless).

**Ephemeral / PR previews** should keep **Valkey/Redis in the preview namespace** (or use key-prefix discipline); do not route previews at `shared-test` without an explicit multi-tenant strategy.

Root [`../kustomization.yaml`](../kustomization.yaml) lists **`shared/production`** and **`shared/test`** before app bundles that depend on this cache.
