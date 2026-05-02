# Clutterstock migration (production)

The migrator runs schema/data migrations against the CNPG `postgres-prod` cluster using `clutterstock-pg-secret/uri`. There is no shared volume with `clutterstock-api`, so the API can stay running during reconciliation.

## New migration image / reruns

Kubernetes Job pod templates are immutable. Bump `metadata.name` in [`job.yaml`](job.yaml) (e.g. `v106` → `v107`) when you change the migrator image or job spec, then reconcile:

```bash
flux reconcile kustomization clutterstock-migrate -n flux-system --with-source
kubectl -n clutterstock-production wait job/clutterstock-migrate-v107 --for=condition=complete --timeout=300s
```

Delete old completed Jobs if names clash with TTL.

## Troubleshooting

- Check Job logs: `kubectl -n clutterstock-production logs job/clutterstock-migrate-v107`
- Confirm the `clutterstock-pg-secret` secret exists and `uri` resolves to the CNPG `postgres-prod` cluster.
