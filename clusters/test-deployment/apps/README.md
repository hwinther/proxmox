# Apps (test namespace)

Deployments pin **semver image tags** (not `latest`) so Flux applies a changed `image:` field and Kubernetes rolls out new pods.

- **Current tag:** `1.0.0` for `ghcr.io/hwinther/test/*` and `ghcr.io/hwinther/clutterstock/*` images.
- **Release workflow:** CI (e.g. GitVersion) builds and pushes `ghcr.io/.../component:<version>`; bump the tag in the matching `*-deployment.yaml` and commit so Flux reconciles.
- **First-time:** ensure each image exists in GHCR as `1.0.0` (retag/push from `latest` if needed) before sync, or ImagePullBackOff until that tag exists.
