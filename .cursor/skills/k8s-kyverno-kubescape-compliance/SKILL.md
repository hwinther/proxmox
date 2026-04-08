---
name: k8s-kyverno-kubescape-compliance
description: >-
  Align new Kubernetes manifests and CI-built images with Kyverno ClusterPolicies
  (wsh-*) and Kubescape configuration scans. Use when adding Deployments, Jobs,
  Helm values, NetworkPolicies, or GHCR publish workflows in this repo.
---

# Kyverno and Kubescape compliance (this repo)

ClusterPolicies live under [`bases/kyverno-platform`](../../../bases/kyverno-platform), [`bases/kyverno-best-practices`](../../../bases/kyverno-best-practices), and [`bases/kyverno-supply-chain`](../../../bases/kyverno-supply-chain); production (and other envs) apply them via `clusters/*/apps/kyverno-policies`. Policies are mostly **Audit** with **background** scans where enabled, so violations show up as PolicyReport failures and in Policy Reporter. Kubescape operator adds **WorkloadConfigurationScanSummary** (e.g. C-0013 non-root, C-0016 privilege escalation, C-0018 readiness, C-0030 NetworkPolicy).

## Checklist for new workloads

1. **Images**
   - Prefer **explicit version tags** (not `:latest`) for every container, initContainer, and ephemeralContainer so **Dependabot** can surface release notes. Kyverno **`wsh-disallow-latest-require-digest`** rejects `:latest` only (Audit); supply-chain **`verifyImages`** rules may **`mutateDigest: true`** to resolve tags to digests at admission where configured.
   - For **CI images** published from this repo to `ghcr.io/hwinther/...`, use [`.github/actions/docker`](../../../.github/actions/docker) with **`attest_supply_chain: "true"`** on the calling workflow and job permissions: `contents: read`, `packages: write`, `id-token: write`, `attestations: write`. That pushes SLSA provenance to the registry and attaches **CycloneDX** + **vuln** Cosign attestations expected by **`wsh-require-github-slsa-provenance`**, **`wsh-require-cyclonedx-sbom`**, and **`wsh-require-cosign-vuln-attestation`**.
   - If an image cannot satisfy a policy yet, add a **narrow** [`PolicyException`](../../../clusters/edge-sdr/apps/adsb-edge-sdr/kyverno-policyexception-hostpath.yaml) (Kyverno `v2`) scoped by **namespace + labels**, not a broad ClusterPolicy change.

2. **Pod and container security**
   - Pod or container: **`runAsNonRoot: true`** where the image supports it.
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
