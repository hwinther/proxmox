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

- `__PR__` — PR number (e.g. `42`)
- `__HOST__` — preview hostname (e.g. `clutterstock-42.preview.wsh.no`)
- `__IMAGE_TAG__` / `__IMAGE_DIGEST__` — despite the names, the **manifest artifact's** tag
  (`pr-<N>`) and digest, `ghcr.io/hwinther/clutterstock/manifests`, as pushed by ClutterStock's
  `pr-e2e.yml`. The artifact pins the api, migrator and frontend images itself.
- `__DB_NAME__` — SQL database name (e.g. `clutterstock_pr42`)

## Where the preview workload comes from

`base/clutterstock-manifests.yaml` holds an `OCIRepository` and a Flux `Kustomization` per preview
namespace. The artifact is the PR's own `deploy/`, rendered exactly like a release but with the PR's
images, so a PR that changes the manifests runs them in its preview before any release. Only
artifacts signed by ClutterStock's `pr-e2e.yml` on a pull-request ref are accepted; test and
production accept release-tag signatures only. The values follow the test tier (shared
`cluttertestdb`, RabbitMQ `test` vhost), with the per-PR database and host patched in by the
overlay. The namespace, network policies, per-preview Valkey and Kyverno-cloned Secrets stay in
this tree.

Editing a template here does not retroactively update existing previews — re-run the workflow on
each open PR (push a commit or re-apply the `deploy-feature` label) to roll templates forward.
