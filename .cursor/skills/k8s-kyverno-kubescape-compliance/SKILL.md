---
name: k8s-kyverno-kubescape-compliance
description: >-
  Align new Kubernetes manifests and CI-built images with Kyverno ClusterPolicies
  (wsh-*) and Kubescape configuration scans. Use when adding Deployments, Jobs,
  Helm values, NetworkPolicies, or GHCR publish workflows in this repo. Covers
  upfront policy decisions and narrow PolicyExceptions to avoid follow-up commits.
---

# Kyverno and Kubescape compliance (this repo)

ClusterPolicies live under [`bases/kyverno-platform`](../../../bases/kyverno-platform), [`bases/kyverno-best-practices`](../../../bases/kyverno-best-practices), and [`bases/kyverno-supply-chain`](../../../bases/kyverno-supply-chain); production (and other envs) apply them via `clusters/*/apps/kyverno-policies`. Many policies are **Audit** with **background** scans, but **treat admission as strict**: missing digests, `:latest`, or invalid security contexts can still **block pod creation** depending on cluster settings and rule overlap, and PolicyReports will show **fail** until resolved. Kubescape operator adds **WorkloadConfigurationScanSummary** (e.g. C-0013 non-root, C-0016 privilege escalation, C-0018 readiness, C-0030 NetworkPolicy).

## Before the first commit (new app / new namespace)

Decide these **while authoring the initial PR**, so you do not chain fixes across multiple merges:

1. **Image reference**
   - Prefer **semver tags** (and digests where you mirror or pin) for every container, initContainer, and ephemeralContainer — **`wsh-disallow-latest-require-digest`** targets `:latest` (see [`bases/kyverno-platform/clusterpolicy-disallow-latest-require-digest.yaml`](../../../bases/kyverno-platform/clusterpolicy-disallow-latest-require-digest.yaml)).
   - If upstream **only** publishes `:latest` (no semver tag to pin): choose **one** path before merge: **(a)** mirror the image to `ghcr.io/hwinther/...` with a semver tag you control, **(b)** pin `image: repo/name@sha256:…` after you compute the digest once, or **(c)** add a **narrow** `PolicyException` for `wsh-disallow-latest-require-digest` **in the same PR** as the workload, with a YAML comment explaining why upstream cannot comply.

2. **`runAsNonRoot` vs image `USER` (kubelet, not Kyverno)**
   - Pod or container **`runAsNonRoot: true`** is required for hygiene and matches **`wsh-require-run-as-non-root`** (Audit in repo defaults), but **kubelet** rejects the pod if the image still runs as **UID 0** and you did not set a non-zero **`runAsUser`** compatible with the image.
   - Before merge: confirm the image’s effective user (Dockerfile `USER`, vendor docs, or `kubectl run … --image=…` once). Either **drop** pod-level `runAsNonRoot` when the image must stay root (accept audit noise for debug-only tools), set **`runAsUser`/`runAsGroup`** that the image supports, or add a **narrow** exception for **`wsh-require-run-as-non-root`** only for initContainers that must chown (same PR as the workload).

3. **Traefik `hostNetwork` + Cilium**
   - Ingress backends are dialed from the **node** identity; workloads often need a **`CiliumNetworkPolicy`** allowing `fromEntities: [host, remote-node]` on the Service port (see [`clusters/production/apps/traefik/README.md`](../../../clusters/production/apps/traefik/README.md) and examples under `clusters/production/apps/*/`).

4. **Init / sidecars**
   - If Helm or your manifest adds **root** initContainers or images that violate supply-chain rules, plan **exceptions + chart values** in the **first** PR (see Headlamp examples under [`clusters/production/apps/headlamp-production`](../../../clusters/production/apps/headlamp-production)).

5. **NetworkPolicy**
   - If the namespace defaults to **deny** or Kubescape **C-0030** matters for you, add ingress/egress in the first PR or document why the app is intentionally wide.

## PolicyExceptions — default deny, narrow allow

**Default:** fix the workload (semver tag, digest pin, non-root-compatible image, probes, limits, labels) instead of exempting policy.

**Use a `PolicyException` only when** the fix is infeasible or disproportionate **and** you can scope it tightly:

- Third-party / upstream images that **only** ship `:latest`, or chart-controlled images you cannot retag in CI yet.
- **InitContainers** that must run as root briefly (copy assets, `chown`).
- **hostPath** / host namespace cases that are truly required (edge hardware, documented).

**Shape (this repo):**

- Kyverno **`PolicyException` `apiVersion: kyverno.io/v2`**, in the **same namespace** as the workload.
- Under **`spec.exceptions`**, list **`policyName`** and concrete **`ruleNames`** (include **`autogen-…`** variants when the policy generates them — mirror [`clusters/production/apps/headlamp-production/kyverno-policyexception-headlamp-plugin-images.yaml`](../../../clusters/production/apps/headlamp-production/kyverno-policyexception-headlamp-plugin-images.yaml)).
- Under **`spec.match`**, scope by **`namespaces`** and **`selector.matchLabels`** on the Pod template label set — **never** a cluster-wide exception.
- **Same commit / same PR** as the Deployment (or HelmRelease) that needs it, with a short comment at the top of the exception file stating **why** the exception exists and **when** to remove it (e.g. “remove when upstream publishes semver tags”).

**Avoid:** copying an exception from another app without matching `ruleNames`, broad namespace-only matches, or silencing policies you could satisfy by changing the image or securityContext.

## Checklist for new workloads

1. **Images**
   - Prefer **explicit version tags** (not `:latest`) for every container, initContainer, and ephemeralContainer so **Dependabot** can surface release notes. Kyverno **`wsh-disallow-latest-require-digest`** forbids `:latest` (see **Before the first commit** if upstream cannot comply).
   - For **CI images** published from this repo to `ghcr.io/hwinther/...`, use [`.github/actions/docker`](../../../.github/actions/docker) with **`attest_supply_chain: "true"`** on the calling workflow and job permissions: `contents: read`, `packages: write`, `id-token: write`, `attestations: write`. That pushes SLSA provenance to the registry and attaches **CycloneDX** + **vuln** Cosign attestations expected by **`wsh-require-github-slsa-provenance`**, **`wsh-require-cyclonedx-sbom`**, and **`wsh-require-cosign-vuln-attestation`**.
   - If an image cannot satisfy a policy yet, add a **narrow** [`PolicyException`](../../../clusters/edge-sdr/apps/adsb-edge-sdr/kyverno-policyexception-hostpath.yaml) (Kyverno `v2`) scoped by **namespace + labels**, not a broad ClusterPolicy change — **together with** the workload in one PR (**PolicyExceptions** section above).

2. **Pod and container security**
   - Pod or container: **`runAsNonRoot: true`** where the image supports it — see **Before the first commit → `runAsNonRoot` vs image `USER`** if the pod fails with **CreateContainerConfigError** (kubelet) while PolicyReports still look green.
   - Every container: **`securityContext.allowPrivilegeEscalation: false`**; prefer **`capabilities.drop: ["ALL"]`** when compatible.
   - Init containers that **must** run as root (e.g. `chmod` on a volume): keep them minimal; add a **PolicyException** for **`wsh-require-run-as-non-root`** (and only what is required) with **`matchLabels`** on the pod template. Example: migrate Jobs in [`clusters/production/apps/clutterstock-migrate`](../../../clusters/production/apps/clutterstock-migrate).

3. **Resources and labels**
   - **`resources.limits.memory`** (and usual CPU/memory requests/limits) on every container — **`wsh-require-resource-limits`** checks memory limits.
   - Pod template label **`app.kubernetes.io/name`** — **`wsh-require-recommended-labels`**.

4. **Probes**
   - Add a **`readinessProbe`** (HTTP or **TCP** on the serving port) for long-lived pods — Kubescape **C-0018**.

5. **NetworkPolicy (Kubescape C-0030)**
   - When you introduce a new namespace or workload class, consider **ingress + egress** rules: allow **DNS** (kube-system, UDP/TCP 53), traffic from **`traefik`** for exposed HTTP routes, in-cluster dependencies by **namespace + pod labels**, and **egress to the internet** only when needed (e.g. OTLP/HTTPS); document why wide egress is used if you keep **`0.0.0.0/0`** with exceptions.
   - Redis and other shared services: restrict **ingress** to known client namespaces. Examples: [`clusters/production/apps/shared/production/networkpolicy-redis.yaml`](../../../clusters/production/apps/shared/production/networkpolicy-redis.yaml).

6. **hostPath / host namespaces**
   - Avoid **`hostPath`**, **`hostNetwork`**, **`hostPID`**, **`hostIPC`** unless required (e.g. edge SDR). Use a scoped **PolicyException** for **`wsh-disallow-host-path`** / host-namespace policies and document the reason.

7. **HelmRelease values**
   - Mirror the same rules for **init containers**, **sidecars**, and **main** images: explicit version tags (not `:latest`), limits, **`podLabels`**, **`securityContext`**, and chart-specific probe fields.

## Reference implementations (production)

| Area | Location |
|------|----------|
| Tagged app images + security + probes + NetworkPolicy | [`clusters/production/apps/clutterstock`](../../../clusters/production/apps/clutterstock) |
| Migrate Job + busybox tag + init exception | [`clusters/production/apps/clutterstock-migrate`](../../../clusters/production/apps/clutterstock-migrate) |
| Headlamp init exceptions + plugin tags | [`clusters/production/apps/headlamp-production`](../../../clusters/production/apps/headlamp-production) |
| Shared Redis / RedisInsight + NP | [`clusters/production/apps/shared`](../../../clusters/production/apps/shared) |
| Docker build + supply-chain attestations | [`.github/actions/docker/action.yaml`](../../../.github/actions/docker/action.yaml), `build-*.yaml` workflows |

## Verification

- Kyverno: Policy Reporter UI (e.g. production **`policy-reporter.mgmt.wsh.no`**) or `kubectl get policyreport -A`.
- Kubescape: `kubectl get workloadconfigurationscansummaries -n <namespace>`.

## Related skills

- [**k8s-deployments**](../k8s-deployments/SKILL.md) — base Deployment/Service layout; combine with this skill for **production** and **policy-clean** manifests (explicit tags; supply-chain policies may mutate to digest at admission).
