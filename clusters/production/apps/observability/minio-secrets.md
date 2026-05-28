# Standalone MinIO credentials (`observability-production`)

The `obs-minio` Deployment and the Loki helmrelease both read MinIO root credentials from the Kubernetes Secret **`obs-minio-root`** in namespace **`observability-production`**. Create it manually (not committed to git) before rollout.

## Required keys

| Key            | Purpose                                                                                  |
| -------------- | ---------------------------------------------------------------------------------------- |
| `rootUser`     | MinIO root username. Used as the S3 `accessKeyId` for Loki and for the bucket-init Job.  |
| `rootPassword` | MinIO root password. Used as the S3 `secretAccessKey`.                                   |

## Create the Secret

```bash
kubectl -n observability-production create secret generic obs-minio-root \
  --from-literal=rootUser="loki-$(openssl rand -hex 4)" \
  --from-literal=rootPassword="$(openssl rand -base64 32 | tr -d '\n')"
```

After the Secret exists, `obs-minio-init-buckets-v001` Job will create the `chunks` and `ruler` buckets, and the Loki pod will pick up the credentials via env vars (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` injected into the helmrelease).

## Rotation

Rotating the password requires updating MinIO **and** restarting Loki so it re-reads the credentials. MinIO root-password rotation is a bit awkward (it's set via env on container start), so the cleanest sequence is:

```bash
# 1. Update the Secret.
kubectl -n observability-production create secret generic obs-minio-root \
  --from-literal=rootUser="<keep-or-change>" \
  --from-literal=rootPassword="$(openssl rand -base64 32 | tr -d '\n')" \
  --dry-run=client -o yaml | kubectl apply -f -

# 2. Restart MinIO so it boots with the new env.
kubectl -n observability-production rollout restart deployment/obs-minio

# 3. Restart Loki so it picks up the new envFrom values.
kubectl -n observability-production rollout restart sts/obs-loki
```

## Background

The standalone MinIO replaces the Loki helm chart's built-in MinIO subchart, which was deprecated and removed by default starting at chart 17.0.0. The long-term plan is to retire this MinIO entirely and use the Proxmox Ceph cluster's RGW endpoint — see the deferred PVE RGW setup notes in the project memory.

## Verify (without printing secret values)

```bash
kubectl -n observability-production describe secret obs-minio-root
```
