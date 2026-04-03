# Environment-scoped shared workloads (production cluster)

Redis (and similar) **shared by multiple apps** on the same **environment line**, not duplicated per product namespace.

| Bundle | Namespace | Consumers (examples) |
|--------|-----------|----------------------|
| [`production/`](production/) | **`shared-production`** | Prod-tier apps (`clutterstock-production`, …) |
| [`test/`](test/) | **`shared-test`** | Test-tier apps (`test-test`, future stable `*.test.wsh.no` workloads) |

Apps point **`REDIS_URL`** at `redis://redis.<namespace>.svc.cluster.local:6379`.

**Ephemeral / PR previews** should keep **Redis in the preview namespace** (or use key-prefix discipline); do not route previews at `shared-test` without an explicit multi-tenant strategy.

Root [`../kustomization.yaml`](../kustomization.yaml) lists **`shared/production`** and **`shared/test`** before app bundles that depend on Redis.
