# Preview-env templates (ddnsadmin)

These files are read by `gitops-preview-upsert.yml` (in `hwinther/reusable-workflows`) and
substituted to produce the per-PR overlay. Placeholders use `__PLACEHOLDER__` syntax and the
workflow substitutes via `sed`.

ddnsadmin is a **single-image** app whose preview image is self-contained (BIND + sqlite + seeded
`example.com` zone baked in by `scripts/start.sh`). Unlike clutterstock there is **no per-PR
database**: this tree intentionally has no `database.yaml.tpl` and no `databases/` subtree, so the
upsert workflow's database step no-ops.

Files the workflow renders per PR:

| Template | Renders to | Purpose |
|---|---|---|
| `overlay.namespace.yaml.tpl` | `../pr-<N>/namespace.yaml` | Per-PR Namespace |
| `overlay.kustomization.yaml.tpl` | `../pr-<N>/kustomization.yaml` | Per-PR kustomize overlay |

Placeholders the workflow replaces:

- `__PR__` — PR number (e.g. `42`)
- `__HOST__` — preview hostname (e.g. `ddnsadmin-42.preview.wsh.no`)
- `__IMAGE_TAG__` / `__IMAGE_DIGEST__` — despite the names, the **manifest artifact's** tag
  (`pr-<N>`) and digest, `ghcr.io/hwinther/ddnsadmin/manifests`, as pushed by ddnsadmin's
  `pr-e2e.yml`. The artifact pins the app image itself.

The multi-image placeholders (`__IMAGE_API_*__`, etc.) and `__DB_NAME__` are unused here.

## Where the preview workload comes from

`base/ddnsadmin-manifests.yaml` holds an `OCIRepository` and a Flux `Kustomization` per preview
namespace. The artifact is the PR's own `deploy/`, so a PR that changes the manifests runs them in
its preview before any release. Previews apply its `./demo` render; production and test apply
`./server`. Only artifacts signed by ddnsadmin's `pr-e2e.yml` on a pull-request ref are accepted;
production accepts release-tag signatures only. The package is private, so the `OCIRepository`
authenticates with the cloned `ghcr-pull` Secret (see `../ghcr-pull-secret.md`).

Editing a template here does not retroactively update existing previews — re-run the workflow on
each open PR (push a commit or re-apply the `deploy-feature` label) to roll templates forward.

> **Draft — needs review before first deploy.** The QA/demo image runs as root and binds `:53` for
> BIND. A restricted PodSecurity / Kyverno admission policy will likely reject it. Either relax PSS
> for `ddnsadmin.wsh.no/preview=true` namespaces or rework the image to run rootless. See the
> security note in ddnsadmin's `deploy/components/demo/deployment-patch.yaml`.
