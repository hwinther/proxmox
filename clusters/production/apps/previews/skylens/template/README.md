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

## Replay + real-auth model (no secrets, no broker)

skylens previews run the backend in **Development** mode for the MQTT replay affordance, but with
**REAL OIDC JWT auth** — so auth regressions (anonymous /hubs 401, in-app sign-in, browser PKCE token
exchange) surface in the preview BEFORE a release tag. Still **no secrets, no mosquitto, no database**:

- **`Mqtt__Replay=true` + `Mqtt__ReplayFile=/app/fixtures/aircraft.json`** — `ReplayMqttTransport`
  replays the fixture baked into the image through the **real** ingest -> SignalR pipeline at 1 Hz, so
  there is no broker and no MQTT credentials. Gated on `Environment.IsDevelopment()`, which is why
  **`ASPNETCORE_ENVIRONMENT=Development` is REQUIRED** in `base/deployment.yaml`.
- **`Auth__Disabled=false` is set EXPLICITLY** — the image's `appsettings.Development.json` bakes
  `Auth:Disabled=true`, so in Development merely omitting the variable silently re-enables DevAuth
  (anonymous `/api/me` returns 200). The explicit env-var false overrides the JSON and wires real
  JwtBearer against `auth.wsh.no` (`Program.cs`: DevAuth needs Development AND `Auth:Disabled`). This needs 443
  egress for OIDC discovery/JWKS (`base/networkpolicies.yaml`) and per-PR redirect URIs on the
  Authelia `skylens` client (see below). The CI e2e compose stack in the skylens repo intentionally
  KEEPS `Auth__Disabled=true` — its Playwright specs assert on anonymous live data.

`FEED__LAT` / `FEED__LON` are the centroid of the replay fixture's aircraft positions rounded to **one
decimal** (~11 km). Precise home coordinates must never appear in this **PUBLIC** repo.

## Auth on preview hosts

Two layers, both real:

- The **Ingress Authelia forward-auth middleware** (`base/ingress.yaml`) gates access to the preview
  host itself.
- **In-app OIDC sign-in works** like production: Authelia can't wildcard redirect URIs, so the
  `skylens` client in `../../authelia-production/authelia-helmrelease.yaml` pre-registers a window of
  `https://skylens-<N>.preview.wsh.no/oauth` entries for upcoming PR numbers — **extend the window
  when the repo's PR/issue counter approaches its end** (or teach the upsert workflow to patch it). A
  PR outside the window still deploys; only in-app sign-in fails (`redirect_uri` rejected). Browser
  PKCE token exchange is covered by `cors.allowed_origins_from_client_redirect_uris` in the Authelia
  OIDC config.

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
