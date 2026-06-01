# ddnsadmin preview GHCR pull secret (`ghcr-pull`)

`ghcr.io/hwinther/ddnsadmin` is a **private** GitHub Container Registry package, so the kubelet
needs a `dockerconfigjson` credential to pull the preview image. (The public `ghcr.io/hwinther/*`
packages like clutterstock pull anonymously and need none of this.)

The credential is created **once, out-of-band**, as the Secret **`ghcr-pull`** in namespace
**`platform-production`** — the same source namespace the other clone policies use. From there the
[`clone-ddnsadmin-preview-secrets`](kyverno-clusterpolicies.yaml) Kyverno ClusterPolicy clones it
into every namespace labeled `ddnsadmin.wsh.no/preview=true`, so each ephemeral per-PR preview ns
gets it automatically. The Deployment references it via `imagePullSecrets` (see
[`base/deployment.yaml`](base/deployment.yaml)).

**Never commit the token or a `*.secret.example.yaml`.** This (public) repo only records the
secret's *name* and how it is consumed.

## Create the source Secret

Use a GitHub Personal Access Token (classic) with the **`read:packages`** scope, or a fine-grained
token scoped to the `ddnsadmin` package with read access:

```bash
kubectl -n platform-production create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username=hwinther \
  --docker-password='<read:packages PAT>' \
  --docker-email='hwinther@wsh.no'
```

Kyverno's background controller already has patch/update on `platform-production` Secrets
(`kyverno-clone-source-secrets` Role) and cluster-wide Secret access
(`kyverno-clusterrole-clone-pbs-encryption-keyfile`), both from the PBS work — so no extra RBAC is
needed for the clone to succeed.

## Verify the clone landed

```bash
kubectl -n ddnsadmin-preview-pr-<N> get secret ghcr-pull
kubectl -n ddnsadmin-preview-pr-<N> get pod -l app=ddnsadmin   # should leave ImagePullBackOff
```

If the source Secret is missing, the clone rule no-ops and the preview pod stays in
`ImagePullBackOff` until you create it.

## Rotate

Recreate the source Secret in `platform-production` (delete + create, or
`kubectl create ... --dry-run=client -o yaml | kubectl apply -f -`). With `synchronize: true` the
ClusterPolicy propagates the change to every existing preview namespace.

## Remove

This whole credential goes away if the `ddnsadmin` GHCR **package** is made public (the GitHub
*repo* can stay private — package visibility is independent). At that point delete the
`clone-ddnsadmin-preview-secrets` policy, the `imagePullSecrets` block, and this Secret.
