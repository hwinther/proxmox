# devops-report secrets

## `ghcr-pull`

The report artifact `ghcr.io/wshno/devops/report` is private (wshno/devops is a private repo), so
the OCIRepository in devops-report-source.yaml pulls it with `ghcr-pull`. The cluster already has
this credential for ddnsadmin (`ghcr-pull` in `platform-production`, see
`../ddnsadmin/base/secrets-bootstrap.md`). Copy it once; the token never leaves the cluster:

```bash
kubectl get secret ghcr-pull -n platform-production -o json \
  | jq '{apiVersion, kind, type, data, metadata: {name: .metadata.name}}' \
  | kubectl create -n devops-report-production -f -
```

The token's account must be able to read wshno's packages (a member of the wshno org, with
`read:packages`). After rotating the source Secret, rerun the pipeline with `kubectl replace` in
place of `kubectl create`. Without the Secret the OCIRepository reports `401 Unauthorized` and the
page stays empty (404); nothing else breaks.
