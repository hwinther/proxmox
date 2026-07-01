# Standardizing first-party app deployments (config in the app repo, light reference here)

Status: **decision pending** — capturing the options to return to. No change made yet.

## Goal

Today, first-party app **code** lives in its own repo (e.g. `hwinther/clutterstock`,
`hwinther/pbs-browser`) but its **Kubernetes manifests** live here in
`clusters/production/apps/<app>/`. The idea under consideration: move the deployment
config/variables into the app repo and keep only a **light reference** in this infra repo, so an app
release + its manifest change is one PR in one repo, and the app's own CI/Renovate can bump its image
tag without a proxmox PR.

Precedent already in this repo: `clusters/production/apps/private-apps/` is exactly a "light
reference" — a Flux `GitRepository` (URL + SSH secret) + a `Kustomization` (path + `sourceRef`) — that
reconciles a whole separate repo. `private-apps` is split for **privacy**; this proposal is the same
mechanism used for **co-location**.

First candidate to pilot this on: **pbs-browser** (see [pbs-encrypted-backup-web-viewer.md](pbs-encrypted-backup-web-viewer.md)).

## The one mechanic that shapes everything

A Flux `Kustomization` builds **one** source tree (`kustomize build` on one path in one source), then
applies `spec.patches` + `spec.postBuild.substitute` on the result. It **cannot** merge the app repo's
manifests with this repo's `bases/netpol-baseline` **component** at build time.

So whatever moves to the app repo, the shared `netpol-baseline` reuse breaks across the repo boundary.
You then either **inline** those 3 policies into the app repo, **template** them (Helm), or keep them
proxmox-side. This is the deciding factor between the options below.

### The clean division: app-config vs cluster-glue

| Belongs in the **app repo** ("how to run it") | Stays in **proxmox** ("cluster glue" / per-cluster values) |
| --------------------------------------------- | ---------------------------------------------------------- |
| Deployment/Service, probes, resources         | Namespace + `pbs.wsh.no/encryption-keyfile` label          |
| Env var **defaults**, container port          | Ingress host + Authelia middleware ref                     |
| The chart (if Helm)                           | `netpol-baseline` (unless templated/inlined into the app)  |
| App-specific NetworkPolicy rules              | Image tag / host / Secret names (as values/substitutions)  |
| (nothing secret — ever)                       | The Kyverno keyfile-clone policy; the out-of-band Secret   |

Secrets stay out-of-band (created via `kubectl`) in **all** options — never in either repo.

## Options

| # | Approach | Light reference in proxmox | netpol-baseline handling | Extra machinery |
| - | -------- | -------------------------- | ------------------------ | --------------- |
| 0 | **Status quo** — manifests in proxmox | (all manifests here) | shared component (as today) | none |
| 1 | Flux **GitRepository** → app repo Kustomize | `GitRepository` + `Kustomization` (~3 small files) | inline in app repo, or remote-base ref | deploy key (if private repo) |
| 2 | Flux **OCIRepository** → OCI Kustomize artifact | `OCIRepository` + `Kustomization` (~2 CRs) | inline in app repo | CI step: `flux push artifact` |
| 3 | **Helm chart** (OCI) + `HelmRelease` | `OCIRepository` + `HelmRelease` (values) | templated in the chart (values toggle) | author + publish + version a chart |

### Option 0 — status quo (current convention)

First-party manifests live in `clusters/production/apps/<app>/` and consume `bases/netpol-baseline`.
Pro: single-pane GitOps — one repo to see/PR all cluster state; components compose locally.
Con: every app image bump is a proxmox PR; config is split from the app.

### Option 1 — Flux GitRepository → app repo (most consistent with `private-apps`)

App repo:
```
deploy/
  kustomization.yaml         # resources below (+ images: tag)
  deployment.yaml            # Deployment + Service
  ingress.yaml               # host/middleware (literal or ${VARS})
  networkpolicy.yaml         # default-deny + dns + app rules (baseline INLINED)
  ciliumnetworkpolicy.yaml   # host/remote-node -> app port
```
proxmox `clusters/production/apps/<app>-production/`:
```
namespace.yaml               # keyfile label — stays here
gitrepository.yaml           # url: hwinther/<app> (+ deploy key if private)
kustomization-<app>.yaml     # Flux Kustomization: sourceRef, path ./deploy, targetNamespace,
                             #   patches / postBuild.substitute for image tag & host
kustomization.yaml           # namespace + the two above
<app>-secrets.md
```
Trade-off: to reuse `netpol-baseline` you'd inline the 3 policies in the app repo, or reference it as a
remote Kustomize base (`components: [github.com/hwinther/proxmox//bases/netpol-baseline?ref=...]`),
which couples the app repo to a proxmox path + ref.

### Option 2 — Flux OCIRepository → OCI Kustomize artifact (lightest; no chart)

Same app-repo `deploy/` layout as Option 1. On release, the app's CI publishes it as an OCI artifact:
```
flux push artifact oci://ghcr.io/hwinther/<app>/manifests:<ver> --path deploy ...
```
proxmox:
```
namespace.yaml               # keyfile label — stays
ocirepository.yaml           # oci://ghcr.io/hwinther/<app>/manifests, ref: semver/tag
kustomization-<app>.yaml     # Flux Kustomization: sourceRef OCIRepository, path ./, targetNamespace,
                             #   postBuild.substitute { IMAGE_TAG, APP_HOST, ... }
kustomization.yaml
<app>-secrets.md
```
Pros: versioned atomically with the image; GHCR-native (already used for images); no second Git source
to authorize. Cons: values are envsubst **strings** (less expressive than Helm); baseline is inlined.

### Option 3 — Helm chart (OCI) + HelmRelease (cleanest "variables in the app repo")

App repo:
```
charts/<app>/
  Chart.yaml                 # version: chart ver; appVersion: image tag
  values.yaml                # ALL defaults: image, resources, probes, env, ingress.host,
                             #   auth.middleware, networkPolicy.* toggles, secretName
  templates/
    deployment.yaml  service.yaml  ingress.yaml
    networkpolicy.yaml         # default-deny + dns + app rules (templated)
    ciliumnetworkpolicy.yaml
```
Publish on release: `helm package` → `helm push … oci://ghcr.io/hwinther/<app>/charts`.
proxmox:
```
namespace.yaml               # keyfile label — stays
ocirepository.yaml           # oci://ghcr.io/hwinther/<app>/charts/<app>
helmrelease.yaml             # chartRef -> OCIRepository; values: { image.tag, ingress.host,
                             #   auth.middleware, pbs.secretName } ; targetNamespace
kustomization.yaml
<app>-secrets.md
```
Pros: parameterizes the cluster glue natively via `values` — the most literal "config lives in the app
repo, values-only reference here". Cons: a chart to author, publish, and version for a single
deployment; this app's netpol stops tracking the shared `bases/netpol-baseline`.

## What stays in proxmox in every option

`namespace.yaml` (with the `pbs.wsh.no/encryption-keyfile` label), the out-of-band per-app Secret, the
Kyverno keyfile-clone policy, and the source/release reference (`GitRepository` / `OCIRepository` +
`Kustomization`/`HelmRelease`). Register the app in `clusters/production/apps/kustomization.yaml` as
today.

## Cross-cutting decisions to settle

- **netpol-baseline**: inline (Options 1/2), template with a values toggle (Option 3), or keep it
  proxmox-side and drop the component for these apps. Whichever — those apps no longer auto-track
  changes to `bases/netpol-baseline`; note that as a tradeoff.
- **Image bumps**: with config in the app repo, the app's own Renovate/CI bumps the tag on release;
  proxmox only pins the source `ref` (chart/artifact/Git tag). This is the main ergonomic win.
- **Pinning**: pin the `OCIRepository`/`GitRepository` `ref` (semver or digest) so reconciles are
  reproducible; let Renovate bump the pin.
- **Convention scope**: decide whether this becomes the standard for **all** first-party apps or a
  one-off for pbs-browser. Splitting one app out is cheap; migrating clutterstock/ddnsadmin/etc. is a
  larger, opt-in effort.

## Leaning (not final)

- Want config truly parameterized as **values** → **Option 3 (Helm)**.
- Want the lightest move that stays in Kustomize and versions with the image → **Option 2 (OCI artifact)**.
- Want the closest match to the existing `private-apps` pattern → **Option 1 (GitRepository)**.

Pilot on **pbs-browser** first, evaluate, then decide whether to standardize the rest.
