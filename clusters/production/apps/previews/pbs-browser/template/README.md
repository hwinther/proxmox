# Preview-env templates (pbs-browser)

Read by `gitops-preview-upsert.yml` (in `hwinther/reusable-workflows`) and substituted to produce
the per-PR overlay. Placeholders use `__PLACEHOLDER__` syntax; the workflow substitutes via `sed`.

Files the workflow renders per PR:

| Template | Renders to | Purpose |
|---|---|---|
| `overlay.namespace.yaml.tpl` | `../pr-<N>/namespace.yaml` | Per-PR Namespace |
| `overlay.kustomization.yaml.tpl` | `../pr-<N>/kustomization.yaml` | Per-PR kustomize overlay |

Placeholders the workflow replaces:

- `__PR__` — PR number (e.g. `42`)
- `__HOST__` — preview hostname (e.g. `pbs-browser-42.preview.wsh.no`)
- `__IMAGE_TAG__` / `__IMAGE_DIGEST__` — the `ghcr.io/hwinther/pbs-browser/app` tag + digest the PR build pushed

pbs-browser previews run the **real `proxmox-backup-client` against PBS** (not `PBS_FAKE`) so a PR can
validate the live browse/restore integration. That means each per-PR namespace gets real credentials:

- the **PBS creds Secret** `pbs-browser-pbs` is cloned from `pbs-browser-production` by
  `../kyverno-clusterpolicies.yaml` (matched on the `pbs-browser.wsh.no/preview` label);
- the **encryption keyfile** is cloned by the existing platform-production
  `clone-pbs-encryption-keyfile` policy (matched on the `pbs.wsh.no/encryption-keyfile` label the
  namespace template sets).

Because a preview can therefore read **real backup contents**, its Ingress is **Authelia-gated**
(`base/ingress.yaml`), same as production. Prefer a read-only / restore-scoped PBS API token in
`pbs-browser-pbs` so ephemeral previews can never mutate the datastore.

There is no `database.yaml.tpl` / `databases/` subtree (no per-PR database). The database step in the
reusable workflow no-ops when `database.yaml.tpl` is absent.

> **GHCR visibility:** the preview pulls `ghcr.io/hwinther/pbs-browser/app` with no `imagePullSecrets`
> (public-package convention, like wshno/clutterstock). If you keep that package **private**, add a
> `ghcr-pull` clone rule to `../kyverno-clusterpolicies.yaml` (see `../ddnsadmin`) and
> `imagePullSecrets` to `base/deployment.yaml`.

Editing a template here does not retroactively update existing previews — push a commit (or re-apply
the `deploy-feature` label) on each open PR to roll templates forward.
