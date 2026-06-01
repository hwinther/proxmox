# Bootstrap secrets for any ddnsadmin instance

Two Secrets need to exist in the instance's namespace (`<NS>` below — e.g. `ddnsadmin-production`,
`ddnsadmin-test`, or whatever you name a new overlay) before its Deployment can start. Neither is
committed to git — create them out-of-band per the recipes below.

## `ddnsadmin-secrets`

Sourced via `envFrom.secretRef` by the Deployment. Carries Django runtime credentials.

| Key                        | Notes                                                                                                                                  |
|----------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| `SECRET_KEY`               | Generate with `python -c 'import secrets; print(secrets.token_urlsafe(64))'`. Rotate to invalidate sessions.                           |
| `DJANGO_SUPERUSER_PASSWORD`| Used once on first boot by `scripts/start.sh`'s idempotent bootstrap. Subsequent re-deploys see the user already exists and no-op.     |

Create:

```bash
kubectl -n <NS> create secret generic ddnsadmin-secrets \
  --from-literal=SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
  --from-literal=DJANGO_SUPERUSER_PASSWORD='<choose-a-strong-password>'
```

Each instance gets its own pair — never reuse `SECRET_KEY` across instances.

## `ghcr-pull`

Image pull credential for the private `ghcr.io/hwinther/ddnsadmin` package. Create per instance:

```bash
kubectl -n <NS> create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username='<github-user-or-bot>' \
  --docker-password='<github-pat-with-read:packages>' \
  --docker-email='<any-email>'
```

The PAT only needs `read:packages`. Rotate by deleting and recreating the Secret.

If you spin up enough instances that manual creation becomes tedious, a Kyverno ClusterPolicy can
clone a single source Secret into any namespace carrying a label — see
`apps/previews/ddnsadmin/kyverno-clusterpolicies.yaml` for the preview-env precedent.

## After first boot

1. Log in as `admin` with `DJANGO_SUPERUSER_PASSWORD` at this instance's ingress host
   (`WEB_PREFIX` env value in the overlay's Deployment patch).
2. Add the **TsigKey** that matches your external BIND server (Database admin → ddnsadmin → Tsig
   keys). Use the same `algorithm` and `secret` configured in BIND's `named.conf` (the `key "..."`
   block). Never reuse the demo key from `scripts/start.sh`.
3. Add the **Zone** rows — `name` = zone (e.g. `wsh.no`), `nameserver` = BIND host/IP, `tsigkey`
   = the TsigKey just created. Different ddnsadmin instances can hold different `Zone` rows
   pointing at the same shared BIND; each instance's DB is independent.
4. From inside the pod (`kubectl -n <NS> exec deploy/ddnsadmin -- python manage.py axfr <zone_id>`)
   to AXFR-import an existing zone, OR add records manually via the UI.

The Django DB is sqlite at `/data/ddnsadmin.db` (RWO PVC), so anything you add survives pod
restarts; the BIND server holds the actual DNS state.
