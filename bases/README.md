# Shared Kustomize bases

Place **environment-agnostic** manifests here (common labels, shared CRD snippets, reusable `resources` sets) and reference them from cluster kustomizations with relative paths, for example:

```yaml
# clusters/production/apps/kustomization.yaml
resources:
  - ../../../bases/example
```

- Keep cluster-specific overlays (names, replicas, secrets) under `clusters/<name>/`. Namespace names should follow **`appname-environment`**. Ingress `host` values should follow **`wsh.no`** patterns (`appname.wsh.no`, `appname.test.wsh.no`, `appname-<pr>.preview.wsh.no`) — see [`.cursor/skills/flux-gitops/SKILL.md`](../.cursor/skills/flux-gitops/SKILL.md).
- Avoid putting secrets in `bases/`; use sealed secrets or SOPS in cluster paths.

Nothing is required to adopt this layout; add subdirectories when the same manifest is duplicated between `test-deployment` and `production`.
