# Preview-env templates (wshno)

Read by `gitops-preview-upsert.yml` (in `hwinther/reusable-workflows`) and substituted to produce
the per-PR overlay. Placeholders use `__PLACEHOLDER__` syntax; the workflow substitutes via `sed`.

Files the workflow renders per PR:

| Template | Renders to | Purpose |
|---|---|---|
| `overlay.kustomization.yaml.tpl` | `../pr-<N>/kustomization.yaml` | Per-PR kustomize overlay |
| `overlay.namespace.yaml.tpl` | `../pr-<N>/namespace.yaml` | Per-PR Namespace |

Placeholders replaced:

- `__PR__` — PR number (e.g. `42`)
- `__HOST__` — preview hostname (e.g. `wshno-42.preview.wsh.no`)
- `__IMAGE_TAG__` / `__IMAGE_DIGEST__` — despite the names, the **manifest artifact's** tag
  (`pr-<N>`) and digest, `ghcr.io/wshno/wshno/manifests`, as pushed by wshno's `pr-e2e.yml`. The
  artifact pins the site image itself.

## Where the preview workload comes from

`base/wshno-manifests.yaml` holds an `OCIRepository` and a Flux `Kustomization` per preview
namespace. The artifact is the PR's own `deploy/` (the Deployment and Service), so a PR that changes
the manifests runs them in its preview before any release. Only artifacts signed by wshno's
`pr-e2e.yml` on a pull-request ref are accepted; production accepts release-tag signatures only. The
Ingress (`base/ingress.yaml`, host patched per PR), the netpols and the namespace stay in this tree.

wshno is a single PUBLIC static image — no per-PR database, secret, or pull credential, so there is
**no** `database.yaml.tpl`, `databases/` subtree, or `kyverno-clusterpolicies.yaml` (unlike
clutterstock/ddnsadmin). The database step in the reusable workflow no-ops when `database.yaml.tpl`
is absent.

Editing a template here does not retroactively update existing previews — push a commit (or re-apply
the `deploy-feature` label) on each open PR to roll templates forward.
