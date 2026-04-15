# Authelia OIDC signing key (`authelia-oidc-jwks`)

Authelia’s OIDC provider uses an **RS256** key pair. The HelmRelease mounts a Kubernetes Secret named `authelia-oidc-jwks` with a PEM file at key `oidc-jwk-rsa.pem` (see `spec.values.secret.additionalSecrets` in `authelia-helmrelease.yaml`). The chart exposes that file at **`/secrets/authelia-oidc-jwks/oidc-jwk-rsa.pem`** in the container; `identity_providers.oidc.jwks[].key.path` must use that **absolute** path so Authelia’s `secret` filter can open it (relative paths are resolved from the process working directory, not from `/secrets`).

That Secret is **not** stored in Git. Create or rotate it on the cluster with the steps below.

## Prerequisites

- `kubectl` configured for the target cluster and namespace `authelia-production`.
- `openssl` (e.g. Git for Windows, WSL, or Linux/macOS).

## Generate a new RSA private key (PEM)

Use a **2048-bit** (or stronger) RSA key. Authelia expects a PKCS#1 PEM private key.

```bash
umask 077
openssl genrsa -out oidc-jwk-rsa.pem 2048
```

Keep `oidc-jwk-rsa.pem` only where you handle cluster credentials; delete the local file when finished if you do not need an offline backup.

Reference: [Authelia — passwords and secrets](https://www.authelia.com/reference/guides/passwords.md) (key handling and hashing for other secrets).

## Create or replace the Secret in the cluster

**First-time create:**

```bash
kubectl create secret generic authelia-oidc-jwks \
  --namespace authelia-production \
  --from-file=oidc-jwk-rsa.pem=./oidc-jwk-rsa.pem
```

**Rotate (replace) an existing Secret:**

```bash
kubectl delete secret authelia-oidc-jwks --namespace authelia-production --ignore-not-found
kubectl create secret generic authelia-oidc-jwks \
  --namespace authelia-production \
  --from-file=oidc-jwk-rsa.pem=./oidc-jwk-rsa.pem
```

Optional label (matches previous in-repo metadata):

```bash
kubectl label secret authelia-oidc-jwks \
  --namespace authelia-production \
  app.kubernetes.io/name=authelia \
  --overwrite
```

## Reload Authelia

So the pod picks up the mounted key:

```bash
kubectl rollout restart deployment/authelia --namespace authelia-production
```

## Verify

```bash
kubectl get secret authelia-oidc-jwks --namespace authelia-production
kubectl describe secret authelia-oidc-jwks --namespace authelia-production
```

You should see one key: `oidc-jwk-rsa.pem`.

## Bootstrap order

If the Secret is missing, the Authelia Deployment may fail to start until you create it. After `kubectl create secret …`, Flux/Helm will reconcile; if the release was already failing, run the `rollout restart` above.

## After rotation

Existing OIDC clients (e.g. Headlamp) may need users to sign in again; any tokens signed with the old key become invalid.
