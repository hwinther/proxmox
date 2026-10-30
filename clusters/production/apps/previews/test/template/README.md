# Preview-env templates

These files are read by `gitops-preview-upsert.yml` (in `hwinther/reusable-workflows`) and
substituted to produce the per-PR overlay + Database CR. Placeholders use `__PLACEHOLDER__` syntax
and the workflow substitutes them with `sed`.

Files that the workflow renders per PR:

| Template                         | Renders to                     | Purpose                      |
| -------------------------------- | ------------------------------ | ---------------------------- |
| `overlay.kustomization.yaml.tpl` | `../pr-<N>/kustomization.yaml` | Per-PR kustomize overlay     |
| `overlay.namespace.yaml.tpl`     | `../pr-<N>/namespace.yaml`     | Per-PR Namespace             |
| `database.yaml.tpl`              | `../databases/pr-<N>.yaml`     | CNPG Database CR for this PR |

Placeholders the workflow replaces:

- `__PR__` — PR number (e.g. `1271`)
- `__HOST__` — preview hostname (e.g. `test-1271.preview.wsh.no`)
- `__IMAGE_TAG__` / `__IMAGE_DIGEST__` — despite the names, the **manifest artifact's** tag
  (`pr-<N>`) and digest, `ghcr.io/hwinther/test/manifests`, as pushed by the test repo's
  `pr-e2e.yml`. The artifact pins the api and frontend images itself.
- `__DB_NAME__` — SQL database name (e.g. `test_pr1271`)

## Where the preview workload comes from

`base/test-manifests.yaml` holds an `OCIRepository` and a Flux `Kustomization` per preview
namespace. The artifact is the PR's own `deploy/`, rendered exactly like a release but with the PR's
images, so a PR that changes the manifests runs them in its preview before any release. Only
artifacts signed by the test repo's `pr-e2e.yml` on a pull-request ref are accepted; the test
environment accepts release-tag signatures only. The values follow the test tier (shared `testdb`,
RabbitMQ `test` vhost), with the per-PR database and host patched in by the overlay. The namespace,
network policies, per-preview Valkey and Kyverno-cloned Secrets stay in this tree.

## Sign-in

The frontend signs in with the `pxce` Authelia client, whose `redirect_uris` must match exactly. The
client carries a fixed pool of preview hosts (see `authelia-helmrelease.yaml`); a PR outside the
pool deploys fine but can't sign in until the pool is moved forward.

Editing a template here does not retroactively update existing previews — re-run the workflow on
each open PR (push a commit or re-apply the `deploy-feature` label) to roll templates forward.
