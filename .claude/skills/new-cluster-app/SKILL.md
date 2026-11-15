---
name: new-cluster-app
description: Checklist for adding or reshaping an app or namespace in the k0s production (or edge-sdr) cluster in this repo, covering namespace, Gateway API route, Authelia, network policies, PBS backups, secrets docs, monitoring, image pinning, manifest artifacts and previews. Use when adding a new app under clusters/*/apps/, onboarding a first-party app's OCI manifests, adding backups, metrics or OIDC to an existing app, or reviewing such a PR.
---

# New app or namespace in the cluster

Flux reconciles `clusters/production` and `clusters/edge-sdr`. Nothing is applied by hand except one-shot Jobs and restores. Use an existing app as the template instead of writing from scratch:
- `clusters/production/apps/node-red-production/`: third-party StatefulSet with PBS backup;
- `pbs-browser-production/` or `skylens-production/`: first-party app from a signed OCI manifest artifact.

**This repo is public.** Don't write private-apps app names, IPs that aren't already public, or secrets into manifests, comments, docs or PR text. Cross-repo wiring uses labels (see Labels below).

## 1. Namespace and placement

- Name it `<app>-<environment>`, for example `foo-production` or `foo-test`. The hostnames:
  - production: `<app>.wsh.no`;
  - test: `<app>.test.wsh.no`;
  - management UIs: `<app>.mgmt.wsh.no`;
  - previews: `<app>-<N>.preview.wsh.no`.
- Create `clusters/production/apps/<ns>/` with a `kustomization.yaml` that sets `namespace:` (the netpol component requires it) and uses `components: [../../../../bases/netpol-baseline]`. Add the directory to `clusters/production/apps/kustomization.yaml` in a sensible position. The order matters for Kyverno clone RBAC; read the comments there.
- **Add the new directory to `.github/dependabot.yml`**, or the "Verify Dependabot cluster directories" check fails. That applies to every new YAML directory under `clusters/`, including `databases/`.
- `namespace.yaml` labels and annotations, as needed:
  - `gateway.wsh.no/traefik: "true"` (may attach HTTPRoutes);
  - annotation `gateway.wsh.no/hostnames: a.wsh.no,b.wsh.no` (exact hostnames the routes may claim; a Kyverno policy enforces it);
  - `app.kubernetes.io/part-of: production`;
  - `pbs.wsh.no/encryption-keyfile: "true"` (only with PBS backups).
- Flux strips namespace labels that are set only by hand. Every label goes through git.

## 2. Routing and auth

- Use a Gateway API `HTTPRoute` to the `traefik` Gateway (namespace `traefik`, `sectionName: web`). Don't add new Ingress objects.
- Forward-auth: an `ExtensionRef` filter to the Middleware `authelia-forwardauth` (traefik.io), which Kyverno puts into labelled namespaces.
- For homepage, add `gethomepage.dev/*` annotations on the route (copy node-red's).
- OIDC clients live in `clusters/production/apps/authelia-production/authelia-helmrelease.yaml`.
  - `redirect_uris` are exact-match, so previews get a fixed pre-registered pool.
  - A client asking for `offline_access` **always** shows consent; give it `lifespan: offline-app`. Tool or Swagger clients should not request `offline_access`.

## 3. Network policy (default deny via netpol-baseline)

The baseline gives default-deny, DNS egress and Prometheus scrape of the standard port. You add the rest:
- **Ingress from Traefik:** Traefik is hostNetwork, so add a CiliumNetworkPolicy with `fromEntities: [host, remote-node]` to the pod port (see `cilium-cluster-nodes-to-http.yaml`). Without it the route returns 504.
- **Metrics on another port:** add an ingress rule from `observability-production` pods `app.kubernetes.io/name: prometheus`.
- **Egress to a ClusterIP Service:** `toPorts` must use the **targetPort**, not the Service port, because Cilium socket-LB rewrites before policy. Check with `kubectl get svc -o yaml`.
- `toEndpoints: [{}]` means **only the policy's own namespace**. For "anywhere in the cluster" use `toEntities: [cluster]`.
- **Apiserver egress** (operators, apps that read Secrets or ConfigMaps via the API): `toEntities: [kube-apiserver]`. A missing rule only shows up when the pod restarts weeks later: a crash loop with empty logs and about 30 seconds runtime.
- **Webhooks or aggregated APIs served from the namespace:** ingress `fromEntities: [host, remote-node, kube-apiserver]`.
- **Pods that query Prometheus:** use the ClusterIP Service on port 9090 plus a dedicated ingress CNP on Prometheus. The NodePort does not work from inside the cluster.
- **Shared services** (postgres-*, shared Redis or Valkey, RabbitMQ) allow consumers by namespace label, so add the new app's label rule on the service side too.
- Run `kubectl get pods --show-labels` before writing selectors for Helm charts; their labels rarely match the obvious guess.
- A multi-namespace kustomization can't use the component. Inline the three floor policies with an explicit `namespace:`.

## 4. Secrets

- Never commit Secret manifests or `*.secret.example.yaml`. Write `<app>-secrets.md` next to the manifests listing each key, with a `kubectl create secret generic ... --from-literal=KEY=...` example (placeholders only). The user creates secrets.
- Postgres credentials, the PBS keyfile, `ghcr-pull` and the preview secrets are cloned by Kyverno GeneratingPolicies. Opt in by label; don't copy them.

## 5. Database (CNPG)

- Use a `Database` CR on the shared cluster (`postgres-production` or `postgres-test`) plus a Kyverno-cloned credential secret. Keep CRs that must stay in another namespace out of an overlay that sets `namespace:`.
- There is no WAL archive. Backups are PBS dumps (CronJob running as uid 1654).

## 6. PBS backup (stateful apps)

Copy node-red's `*-pbs-backup-cronjob.yaml`, `*-pbs-restore-job.yaml` (applied by hand, not listed in the kustomization) and `*-pbs-backup-secrets.md`:
- **`runAsUser`/`runAsGroup` = the app's uid/gid** (or PUID/PGID for linuxserver images), with `runAsNonRoot` and caps dropped. Root without caps silently skips mode-0600 files, and the job still says Complete.
- The Secret always sets `PBS_ENCRYPTION_PASSWORD`. The keyfile is cloned via the namespace label and mounted at `/etc/pbs/keyfile`.
- `PBS_NAMESPACE=Production/k0s` for new apps; tell snapshots apart by `hostname:`.
- **Volume pods:** set required podAffinity to the app pod (RWO PVC) and `concurrencyPolicy: Forbid`. **Game servers or anything that hibernates:** use preferred affinity, `activeDeadlineSeconds: 3600` and the `pbs.wsh.no/suspend-backup-when-hibernated` label.
- The same CronJob pattern is duplicated in private-apps. A change to the pattern (image, securityContext, schedule) goes in both repos.

## 7. Images

- First-party (`ghcr.io/hwinther/*`, `ghcr.io/wshno/*`): **semver tag only** in git. Kyverno's ImageValidatingPolicy adds the digest and verifies the SLSA signature (Deny), so expect git-vs-live drift on `.image`. Third-party: tag-pinned. `:latest` is not allowed.
- **First-party app with a `deploy/` dir:** use an `OCIRepository` plus a Flux `Kustomization` for `ghcr.io/<owner>/<app>/manifests` (copy `<app>-manifests.yaml`).
  - cosign `matchOIDCIdentity` pins the signer workflow: `container.yml@refs/tags/v*` for prod, `promote.yml@refs/heads/main` where promotion is used, `pr-e2e.yml@refs/pull/N/merge` for previews.
  - Renaming the app's workflow breaks verification.
  - New wshno-org packages start private; the user makes them public in the UI.
- After a base image switch to distroless, check the consumers' `command:` for `/bin/sh`.

## 8. Jobs

- Flux-owned Jobs get **no `ttlSecondsAfterFinished`**: TTL plus Flux equals a daily re-run.
- To re-run a Job, bump `metadata.name`. The "Verify Kubernetes Job name bump" check enforces this for `job.yaml`.

## 9. Monitoring

- Add a ServiceMonitor or PodMonitor plus the netpol rule (section 3).
- PrometheusRules:
  - template functions are `toLower`/`toUpper`/`humanize*`, not `lower`;
  - **one invalid rule fails the whole Flux apply**, so dry-run first: `kubectl apply --dry-run=server -f <rule>`;
  - Flux 2.8 has no `gotk_reconcile_condition`.
- Grafana dashboards: if you change a dashboard's `uid`, also rename the file, or the old one is orphaned and both return 500.

## 10. Previews (first-party apps with PR previews)

- Create `clusters/production/apps/previews/<app>/{base,databases,template}` plus a `previews-<app>` Kustomization in `flux-system/gotk-sync.yaml`.
- Add the Authelia redirect pool, the `<app>.wsh.no/preview=true` rules on each shared service, and a nightly host if wanted.
- Use `labels:` with `includeSelectors: false`, never `commonLabels`, because it breaks netpol peer selectors.

## Verify before you call it done

- `kubectl kustomize clusters/production/apps/<ns>` renders, and `kubectl apply --dry-run=server -k` passes when you have cluster access.
- The PR's Manifest diff comment shows only the intended objects.
- After merge, run `flux reconcile kustomization flux-system --with-source`, then check the Kustomization is Ready and the pods are Running.
- `curl` the route; for SPAs, curl a **hashed asset**, not just `/`.
- Check `hubble_drop_total{reason="POLICY_DENIED"}` for the namespace.
- Run a manual backup Job and confirm the log has no `access denied` lines and a sensible size.
- PR title as a Conventional Commit, for example `feat(foo): deploy foo to production`.
