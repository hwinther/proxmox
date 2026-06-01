# Bootstrap secrets for ddnsadmin-production

Two Secrets need to exist in `ddnsadmin-production` before the Deployment can start. Neither is
committed to git — create them out-of-band per the recipes below.

## `ddnsadmin-secrets`

Sourced via `envFrom.secretRef` by the Deployment. Carries Django runtime credentials that the
container needs at startup.

| Key                       | Notes                                                          |
|---------------------------|----------------------------------------------------------------|
| `SECRET_KEY`              | Generate with `python -c 'import secrets; print(secrets.token_urlsafe(64))'`. Rotate to invalidate sessions. |
| `DJANGO_SUPERUSER_PASSWORD` | Used once on first boot by `scripts/start.sh`'s idempotent bootstrap. Subsequent re-deploys see the user already exists and no-op. |

Create:

```bash
kubectl -n ddnsadmin-production create secret generic ddnsadmin-secrets \
  --from-literal=SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
  --from-literal=DJANGO_SUPERUSER_PASSWORD='<choose-a-strong-password>'
```

## `ghcr-pull`

Image pull credential for the private `ghcr.io/hwinther/ddnsadmin` package. Same Secret as the
preview-env path; either clone it via a Kyverno ClusterPolicy (mirroring
`clone-ddnsadmin-preview-secrets` in `apps/previews/ddnsadmin/kyverno-clusterpolicies.yaml`), or
create it directly here:

```bash
kubectl -n ddnsadmin-production create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username='<github-user-or-bot>' \
  --docker-password='<github-pat-with-read:packages>' \
  --docker-email='<any-email>'
```

The PAT only needs `read:packages`. Rotate by deleting and recreating the Secret.

## After first boot

1. Log in as `admin` with `DJANGO_SUPERUSER_PASSWORD` at `https://ddns.wsh.no`.
2. Add the **TsigKey** that matches your external BIND server (Database admin → ddnsadmin → Tsig
   keys). Use the same `algorithm` and `secret` you've configured in `named.conf` (the `key "..."`
   block). Don't reuse the demo key.
3. Add the **Zone** rows — `name` = zone (e.g. `wsh.no`), `nameserver` = BIND host/IP, `tsigkey`
   = the TsigKey just created.
4. `python manage.py axfr <zone_id>` from inside the pod to AXFR-import the existing zone, OR add
   records manually via the UI.

The Django DB is sqlite at `/data/ddnsadmin.db` (RWO PVC), so anything you add survives pod
restarts; the BIND server holds the actual DNS state.
