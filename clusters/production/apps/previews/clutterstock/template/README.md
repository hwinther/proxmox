# Preview-env templates

These files are read by `gitops-preview-upsert.yml` (in `hwinther/reusable-workflows`) and
substituted to produce the per-PR overlay + Database CR. Placeholders use `{{PLACEHOLDER}}` syntax
and the workflow uses `envsubst`-style substitution via `sed`.

Files that the workflow renders per PR:

| Template | Renders to | Purpose |
|---|---|---|
| `overlay.kustomization.yaml.tpl` | `../pr-<N>/kustomization.yaml` | Per-PR kustomize overlay |
| `overlay.namespace.yaml.tpl` | `../pr-<N>/namespace.yaml` | Per-PR Namespace |
| `database.yaml.tpl` | `../databases/pr-<N>.yaml` | CNPG Database CR for this PR |

Placeholders the workflow replaces:

- `__PR__` — PR number (e.g. `42`)
- `__HOST__` — preview hostname (e.g. `clutterstock-pr-42.test.wsh.no`)
- `__IMAGE_API_TAG__` — API image tag (e.g. `0.27.0-pr.42`)
- `__IMAGE_API_DIGEST__` — API image digest (e.g. `sha256:abc...`)
- `__IMAGE_FRONTEND_TAG__` / `__IMAGE_FRONTEND_DIGEST__`
- `__IMAGE_MIGRATOR_TAG__` / `__IMAGE_MIGRATOR_DIGEST__`
- `__DB_NAME__` — SQL database name (e.g. `clutterstock_pr42`)

Editing a template here does not retroactively update existing previews — re-run the workflow on
each open PR (push a commit or re-apply the `deploy-feature` label) to roll templates forward.
