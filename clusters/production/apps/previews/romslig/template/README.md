# Preview-env templates

These files are read by `gitops-preview-upsert.yml` (in `hwinther/reusable-workflows`) and
substituted to produce the per-PR overlay. Placeholders use `__PLACEHOLDER__` syntax and the workflow
substitutes them with `sed`.

| Template                         | Renders to                     | Purpose                  |
| -------------------------------- | ------------------------------ | ------------------------ |
| `overlay.kustomization.yaml.tpl` | `../pr-<N>/kustomization.yaml` | Per-PR kustomize overlay |
| `overlay.namespace.yaml.tpl`     | `../pr-<N>/namespace.yaml`     | Per-PR Namespace         |

There is no `database.yaml.tpl`: a romslig preview has no database (see `../kustomization.yaml`).

Placeholders the workflow replaces:

- `__PR__`: PR number (e.g. `42`), or `nightly` for wshno/romslig's nightly-preview.yml
- `__HOST__`: preview hostname (e.g. `romslig-42.preview.wsh.no`)
- `__IMAGE_TAG__` / `__IMAGE_DIGEST__`: despite the names, the **manifest artifact's** tag (`pr-<N>`
  or `main`) and digest, `ghcr.io/wshno/romslig/manifests`, as pushed by romslig's `pr-e2e.yml`. The
  artifact pins the api and web images itself.

## Where the preview workload comes from

`base/romslig-manifests.yaml` holds an `OCIRepository` and a Flux `Kustomization` per preview
namespace. The artifact is the PR's own `deploy/`, rendered exactly like a release but with the PR's
images, so a PR that changes the manifests runs them in its preview before any release. Only artifacts
signed by romslig's `pr-e2e.yml` on a pull-request ref or on main are accepted; production accepts
release-tag signatures only.

Access: `romslig-<N>.preview.wsh.no` (and `romslig-nightly`) are limited to LDAP group
`romslig-users` in Authelia (`../../../authelia-production/authelia-helmrelease.yaml`), like
production. `/api/health` bypasses Authelia so the workflows can wait for readiness.

Editing a template here does not retroactively update existing previews: re-run the workflow on each
open PR (push a commit or re-apply the `deploy-feature` label) to roll templates forward.
