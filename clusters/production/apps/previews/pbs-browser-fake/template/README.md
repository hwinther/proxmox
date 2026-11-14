# Fake-data env templates (pbs-browser)

Read by `gitops-preview-upsert.yml` (in `hwinther/reusable-workflows`) when pbs-browser's
`nightly-preview.yml` deploys with `preview_base_path: clusters/production/apps/previews/pbs-browser-fake`
and `pr_number: nightly`. Same placeholders as `../../pbs-browser/template`:

| Template                         | Renders to                       |
| -------------------------------- | -------------------------------- |
| `overlay.namespace.yaml.tpl`     | `../pr-nightly/namespace.yaml`     |
| `overlay.kustomization.yaml.tpl` | `../pr-nightly/kustomization.yaml` |

- `__PR__`: `nightly`, giving namespace `pbs-browser-fake-nightly`
- `__HOST__`: `pbs-browser-nightly.preview.wsh.no`
- `__IMAGE_TAG__` / `__IMAGE_DIGEST__`: the manifest artifact's tag (`main`) and digest

## Why a separate tree

The PR previews (`../../pbs-browser`) run the real `proxmox-backup-client` against PBS, with the
credentials and encryption keyfile cloned in, so they can read real backups. The nightly e2e run signs
in with a shared e2e user, which must never reach those. Envs here run the same signed artifact with
cluster-side patches instead (`base/pbs-browser-manifests.yaml`):

- `PBS_FAKE=1` and the `pbs-browser-pbs` envFrom removed: the app serves its built-in sample data
  (`FakePbsClient`), the same data the compose e2e run asserts on;
- the namespace carries none of the clone labels (`pbs-browser.wsh.no/preview`,
  `pbs.wsh.no/encryption-keyfile`), so Kyverno clones nothing;
- the netpol has no egress to PBS;
- only main's signature (`pr-e2e.yml@refs/heads/main`) is accepted.

Authelia: `pbs-browser-nightly.preview.wsh.no` stays on the default two_factor (any user, so the e2e
user too), and `/healthz` there bypasses forward-auth for the workflow's readiness wait.
