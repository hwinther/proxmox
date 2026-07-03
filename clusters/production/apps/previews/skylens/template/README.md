# Preview-env templates (skylens)

Read by `gitops-preview-upsert.yml` (in `hwinther/reusable-workflows`) and substituted to produce
the per-PR overlay. Placeholders use `__PLACEHOLDER__` syntax; the workflow substitutes via `sed`.

Files the workflow renders per PR:

| Template                         | Renders to                     | Purpose                  |
| -------------------------------- | ------------------------------ | ------------------------ |
| `overlay.namespace.yaml.tpl`     | `../pr-<N>/namespace.yaml`     | Per-PR Namespace         |
| `overlay.kustomization.yaml.tpl` | `../pr-<N>/kustomization.yaml` | Per-PR kustomize overlay |

Placeholders the workflow replaces:

- `__PR__` — PR number (e.g. `42`)
- `__HOST__` — preview hostname (e.g. `skylens-42.preview.wsh.no`)
- `__IMAGE_TAG__` / `__IMAGE_DIGEST__` — the `ghcr.io/hwinther/skylens/api` tag + digest the PR build pushed

## Replay + DevAuth model (no secrets, no broker)

skylens previews run the backend in **Development** mode, which unlocks two built-in affordances that
let a PR run end-to-end with **no secrets, no mosquitto, no external egress, and no database**:

- **`Auth__Disabled=true`** — swaps JwtBearer for `DevAuthHandler`, which stamps a fixed principal, so
  no OIDC round-trip and no Authelia client/redirect URIs are needed.
- **`Mqtt__Replay=true` + `Mqtt__ReplayFile=/app/fixtures/aircraft.json`** — `ReplayMqttTransport`
  replays the fixture baked into the image through the **real** ingest -> SignalR pipeline at 1 Hz, so
  there is no broker and no MQTT credentials.

Both are gated on `Environment.IsDevelopment()` in `Program.cs`, which is why
**`ASPNETCORE_ENVIRONMENT=Development` is REQUIRED** in `base/deployment.yaml` — without it the app
ignores these flags and reverts to demanding real OIDC + a live broker, breaking the preview.

`FEED__LAT` / `FEED__LON` are the centroid of the replay fixture's aircraft positions rounded to **one
decimal** (~11 km). Precise home coordinates must never appear in this **PUBLIC** repo.

## Auth on preview hosts

The app runs auth-less (DevAuth auto-authenticates every request), so the **Ingress Authelia
forward-auth middleware is the only access gate** for preview hosts (`base/ingress.yaml`) — the
opposite of production, which stays public and validates real OIDC JWTs in-app. **In-app OIDC sign-in
is intentionally nonfunctional on preview hosts**: there are no Authelia redirect URIs registered for
`*.preview.wsh.no`, and none are needed because the forward-auth middleware gates access instead.

## Host / namespace naming

- Namespace: `skylens-preview-pr-<N>`
- Host: `skylens-<N>.preview.wsh.no` (patched into the Ingress by the overlay)

## Teardown

`gitops-preview-teardown.yml` removes the `pr-<N>` entry from `../kustomization.yaml` when the PR is
closed; Flux (`prune: true`) then deletes the namespace and all its resources.

There is no `kyverno-clusterpolicies.yaml`, no `database.yaml.tpl`, and no `imagePullSecrets`: the
preview needs no cloned secret, no per-PR database, and pulls the **public** package
`ghcr.io/hwinther/skylens/api` with no credential (public-package convention, like wshno/clutterstock).

Editing a template here does not retroactively update existing previews — push a commit (or re-apply
the `deploy-feature` label) on each open PR to roll templates forward.
