# k0s with Cilium on Proxmox (homelab guide)

This guide is tailored for a **multi-node** k0s cluster on Proxmox VMs, using **Cilium** as the CNI. It incorporates corrections to common blog examples (API endpoint for workers, CoreDNS, version pinning).

**Official references:**

- [k0s networking (custom CNI)](https://docs.k0sproject.io/stable/networking/)
- [k0s configuration (`spec.network`)](https://docs.k0sproject.io/stable/configuration/#specnetwork)
- [Cilium Helm installation](https://docs.cilium.io/en/stable/installation/k8s-install-helm/)

---

## 1. Plan addresses before installing

| Range | Typical default | Check |
|--------|-----------------|--------|
| **Pod CIDR** | e.g. `10.244.0.0/16` | Must **not** overlap Proxmox LAN, storage networks, or **Ceph public/cluster** subnets |
| **Service CIDR** | e.g. `10.96.0.0/12` | Same as above — unique on your estate |
| **API server** | TCP **6443** on controller(s) | Workers and CLI use this; pick a **stable** target (see §5) |
| **Konnectivity** | TCP **8132** (k0s) | Required worker → controller path per [k0s networking](https://docs.k0sproject.io/stable/networking/) |

Changing CNI **after** the cluster is initialized is effectively a **redeploy** for k0s — choose **`provider: custom`** and Cilium **from day one** if that is your target.

---

## 2. Node prerequisites

- **Linux kernel** meets the **minimum for your Cilium version** (Cilium docs list this per release).
- **No stale CNI config** on workers (`/etc/cni/net.d/` should be managed by whatever installs after k0s — avoid leftovers from old tests).
- **MTU** if you use overlay networking (VXLAN/Geneve): account for overhead on the Proxmox bridge so you do not black-hole large packets.
- **Firewall:** on workers allow **outbound** to controllers: **6443** (Kubernetes API) and **8132** (Konnectivity). Allow traffic involving **pod CIDR** and **service CIDR** as in k0s firewalld examples if you use host firewalls.

---

## 3. k0s `ClusterConfig` outline

Use **`spec.network.provider: custom`** so k0s does not install kube-router. Install **Cilium yourself** (Helm or manifests) once the API server is up.

**Disable kube-proxy only if** you enable **Cilium kube-proxy replacement** for the same k0s/Cilium versions you run — verify in both projects’ docs for your pair.

Example shape (field names **must** match your **k0s version** — open the versioned docs if something fails validation):

```yaml
apiVersion: k0s.k0sproject.io/v1beta1
kind: ClusterConfig
metadata:
  name: k0s
spec:
  network:
    provider: custom
    podCIDR: 10.244.0.0/16      # adjust — no overlap with LAN/Ceph
    serviceCIDR: 10.96.0.0/12   # adjust
    kubeProxy:
      disabled: true            # only with Cilium kube-proxy replacement; else omit/false
```

### CoreDNS

**Do not disable CoreDNS** based on generic “Cilium manages DNS” comments. Cilium is **not** a substitute for **cluster DNS** (CoreDNS). Keep k0s’ normal DNS stack unless you have a **documented** alternative.

### Aggregated APIs (`APIService`) when kube-proxy is disabled

With **`spec.network.kubeProxy.disabled: true`**, the kube-apiserver process usually **does not** have kube-proxy rules on the host to reach **Service ClusterIPs**. Extension API servers register an **`APIService`** that points at a **Service** (for example **metrics-server** → `metrics.k8s.io`, or **Kubescape storage** → `spdx.softwarecomposition.kubescape.io`). Discovery then fails with **`FailedDiscoveryCheck`**, often surfaced as:

- `kubectl get apiservice` → `False (FailedDiscoveryCheck)` and a message like  
  `Get "https://<service-cluster-ip>:443/...": No agent available`
- UIs (e.g. **Headlamp**) returning **503** on paths under  
  `/apis/spdx.softwarecomposition.kubescape.io/...`
- `kubectl api-resources` **omitting** those API groups (so `kubectl get workloadconfigurationscans` says the resource type does not exist)
- **Kyverno** (and other **admission webhooks** that target a `Service` ClusterIP): `kubectl apply` / Flux dry-run fails with **`No agent available`** when calling webhooks such as `mutate-policy.kyverno.svc` or `mutate.kyverno.svc-fail` — the control plane often cannot open a working path to those **Service** VIPs without kube-proxy. **`--enable-aggregator-routing`** (below) **does not** fix this path: it only affects how the **aggregation layer** reaches extension API servers registered via **`APIService`**, not how the apiserver dials **admission** webhooks. This repo uses **Kyverno `admissionController.hostNetwork: true`** and a non-default **`webhookServer.port`** (see `clusters/*/apps/kyverno/kyverno-helmrelease.yaml`) as the practical workaround. With **hostNetwork**, Kyverno’s **metrics** port (chart default **8000**) is also bound on the **node** and collides with **Traefik** (same repo: `web` on **8000**), which surfaces as **`didn't have free ports`** scheduling failures — override **`admissionController.metering.port`**, align **health probes** with **`webhookServer.port`**, and use **`updateStrategy.rollingUpdate.maxSurge: 0`** so rollouts do not run two admission pods on one node.

Kubernetes documents that if kube-proxy is **not** running on the same host as the API server, you should set **`--enable-aggregator-routing=true`** on **kube-apiserver** so aggregation traffic is routed to **endpoint IPs** instead of ClusterIPs. In k0s, add this under **`spec.api.extraArgs`** in your controller `k0s.yaml`, then **restart k0s on each controller** (or your usual roll) so the apiserver process reloads with the new flags:

```yaml
spec:
  api:
    extraArgs:
      enable-aggregator-routing: "true"
```

See also [Configure the aggregation layer](https://kubernetes.io/docs/tasks/extend-kubernetes/configure-aggregation-layer/) (note near the end on **enable-aggregator-routing**). The repo example [`k0s.yaml.example`](k0s.yaml.example) includes this flag next to **Cilium + kube-proxy disabled**.

#### Verifying the *running* apiserver (not only `k0s.yaml`)

There is **no** cluster API that lists kube-apiserver flags. Use the **controller node** and/or **indirect** checks:

| What | How |
|------|-----|
| **Config file syntax** | On a controller: `sudo k0s config validate --config /etc/k0s/k0s.yaml` (catches YAML/schema issues; does not prove the running process matched the file before restart). |
| **Process command line** | On **each** controller, k0s runs **kube-apiserver** on the host. Inspect argv, e.g. `pgrep -af kube-apiserver` or `tr '\0' ' ' < /proc/$(pgrep -o -f kube-apiserver)/cmdline` and confirm **`--enable-aggregator-routing=true`** appears. |
| **Indirect (aggregation target)** | `kubectl describe apiservice v1beta1.spdx.softwarecomposition.kubescape.io` (or `… -o yaml`): if **`FailedDiscoveryCheck`** URLs use a **pod IP** (e.g. `https://10.244.x.x:8443/...`) instead of a **Service ClusterIP** (an address inside your **`serviceCIDR`**), aggregator routing is **likely** active; **`No agent available`** then points at **Konnectivity** / path to pod network, not a missing flag. |

If discovery still fails after that, treat it as **Konnectivity or host firewall**: ensure workers reach controllers on **8132**, and review k0s networking / firewalld notes (similar symptoms appear when the control plane cannot open paths to pod/service networks).

#### Kyverno admission webhooks and hostNetwork

Kyverno’s **MutatingWebhookConfiguration** / **ValidatingWebhookConfiguration** still reference **`clientConfig.service`** (for example `kyverno-kyverno-svc.kyverno.svc`, Service port **443**). The Service’s **`targetPort`** is the named port **https**, which maps to **`admissionController.webhookServer.port`** on the pod (this repo uses **10443** when **hostNetwork** is on). The apiserver therefore dials the **Service ClusterIP:443**; Cilium’s kube-proxy replacement must translate that on **controller** hosts the same way it does on workers.

If **`kubectl apply`** or **Flux** keeps failing with **`No agent available`** to `https://…kyverno…svc:443/…` after enabling **hostNetwork**:

1. Confirm **Cilium runs on every controller** and **kube-proxy replacement** is healthy (`cilium status` on controllers).
2. Compare **`kubectl get endpoints -n kyverno kyverno-kyverno-svc -o wide`** with your **`webhookServer.port`** — addresses should be **node IPs** with that port, not stale pod IPs.
3. Treat persistent failures as **no dataplane path from the apiserver host to Service CIDR** (firewall, Cilium-only-on-workers, or misconfigured **`k8sServiceHost`** / **`kubeProxyReplacement`**) rather than a wrong Kyverno port on the Service object.

As a **stop-gap** when admission must stay available (Flux, Helm, migrate Jobs), Kyverno **`features.forceFailurePolicyIgnore.enabled`** makes webhook **call failures** non-blocking; **policy decisions still apply when the webhook is reachable**. This repo enables it in **`clusters/*/apps/kyverno/kyverno-helmrelease.yaml`** until **Konnectivity (8132)** and **Service VIP reachability from controllers** are confirmed; set **`enabled: false`** again after that. See upstream issues for edge cases.

#### Kubescape `node-agent` on k0s controllers

The **kubescape-operator** chart’s **node-agent** DaemonSet only picks up control-plane **tolerations** if you set **`nodeAgent.tolerations`** or **`customScheduling.tolerations`**. **hostScanner** ships default control-plane tolerations; **node-agent** does not. Without them, Helm can time out waiting for **node-agent** on single-node or control-plane-only taints. This repo sets **`customScheduling.tolerations`** in `clusters/production/apps/kubescape-production/kubescape-operator-helmrelease.yaml`.

---

## 4. Bootstrap order (recommended)

1. **Install and start** the first **controller** with the config above (k0sctl or `k0s install controller --config …`).
2. Obtain **admin kubeconfig** and confirm **API responds** (`kubectl get nodes` may show only controller or NotReady until CNI exists — that can be expected briefly).
3. **Install Cilium** with Helm (or pinned manifests) from a machine with `KUBECONFIG` set.
4. Wait until **Cilium** (and the Cilium **operator**) are **Ready**.
5. **Join workers** with valid tokens; confirm nodes become **Ready**.
6. Run **connectivity checks** (`cilium status`, optional `cilium connectivity test` if CLI installed).

   **SSH / kubeconfig:** The `cilium` CLI queries the API the same way as **`kubectl`** (via **`KUBECONFIG`**). If you run `cilium status` on a shell with **no** kubeconfig, client-go falls back to **`http://localhost:8080`**, you get **`dial tcp [::1]:8080: connect: connection refused`**, and the summary shows **errors** for Cilium, Envoy, and the operator even when the dataplane on that node is fine. **Fix:** point **`KUBECONFIG`** at a file whose **`server:`** URL is reachable **from that host** (not `127.0.0.1:6443` on workers unless the API really listens there).

   | Node role | Typical approach |
   |-----------|------------------|
   | **Controller** | `export KUBECONFIG=/var/lib/k0s/pki/admin.conf` (default k0s data dir), or `sudo k0s kubeconfig admin > "$HOME/.kube/config"` once, then `cilium status`. |
   | **Worker** | **`admin.conf` is usually not on workers** — use a kubeconfig copied from a controller (with **`server:`** set to the same API endpoint Cilium uses, e.g. your stable controller IP **`6443`**), or run **`cilium status`** only from a machine that already has cluster admin access. |

   **`DaemonSet Ready` but `cilium` shows errors / `error dialing backend: No agent available`:** The summary can still show **Cilium: N errors** while **DaemonSets are 3/3** and **Cluster Pods … managed by Cilium** looks healthy. In that case the CLI has already talked to the API successfully; the errors come from **`kubectl exec`** (or equivalent) into each **cilium-agent** pod to run **`cilium-dbg status`** inside the container. That path is **API server → kubelet** streaming. On **k0s**, broken **Konnectivity** (workers must reach controllers on **TCP 8132**, see the table in §1) often surfaces as **`No agent available`** for **`kubectl exec`**, **`kubectl logs`**, and the same for **Kyverno webhooks** / **aggregated APIs** that need a working control-plane-to-node path. **Checks:** confirm **`kube-system`** pods **konnectivity-agent** (per node) and **konnectivity-server** (controllers) are **Running**; from a worker, `nc -zv <controller-ip> 8132` (or your **`agentPort`**); review host firewalls (§1). **Workaround to inspect one node without exec:** on that host, use **`crictl`** / **`ctr`** to **exec** into the **cilium** container and run **`cilium-dbg status`** (or use Cilium’s host-mounted debug socket if your install exposes it).

Joining workers **before** Cilium runs can leave nodes without a working pod CNI — prefer **Cilium on the control plane API** as soon as the API is usable, **then** expand workers.

---

## 5. Cilium Helm values that matter (multi-node)

### `k8sServiceHost` / `k8sServicePort`

For **kube-proxy replacement**, Cilium needs the **Kubernetes API** address as seen **from every node** (including **workers**).

| Wrong | Right |
|--------|--------|
| `127.0.0.1` on workers | Workers are not the API server — `127.0.0.1` points at **the wrong host** |

**Use one of:**

- **Stable controller IP** (private LAN) — simplest homelab option  
- **DNS name** resolving to that IP  
- **Load balancer / VIP** for HA control plane (future)  
- **`k8sServiceHostRef`** (Cilium Helm) pointing at a **ConfigMap** that holds host/port, if you automate endpoint discovery — see [Cilium Helm reference](https://docs.cilium.io/en/stable/helm-reference/) for your chart version.

Set **`k8sServicePort`** to **`6443`** unless your install uses a non-default apiserver port.

Avoid assuming **`k8sServiceHost: auto`** works on k0s the same way as on kubeadm clusters unless you confirm what k0s publishes in `kube-public` or similar.

### Other typical knobs

- **`kubeProxyReplacement: true`** only alongside **disabled kube-proxy** in k0s and a **supported** Cilium configuration for your Kubernetes version.
- **`ipam.mode: kubernetes`** aligns with k0s advertising **pod CIDR** to the control plane.
- **Tunnel / datapath** (`tunnel`, `routingMode`, etc.): pick what your Cilium version and kernel support; **VXLAN** is a common default in examples.
- **Small clusters:** `operator.replicas: 1` reduces overhead (not for large HA operator setups).

**Pin** the **Cilium chart version** to a release **tested** with your **exact** k0s (Kubernetes) version.

Example **illustrative** Helm install (replace `<API_HOST>` and chart version):

```bash
helm repo add cilium https://helm.cilium.io/
helm repo update
helm upgrade --install cilium cilium/cilium \
  --namespace kube-system \
  --version <CHART_VERSION> \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost=<API_HOST> \
  --set k8sServicePort=6443 \
  --set ipam.mode=kubernetes \
  --set operator.replicas=1
```

---

## 6. Verify

```bash
kubectl -n kube-system get pods -l k8s-app=cilium
# With Cilium CLI:
cilium status
# Optional full test:
# cilium connectivity test
```

Confirm **DNS**: a short-lived pod that resolves `kubernetes.default` and a `Service` name in your namespace.

### metrics-server / pods → `kubernetes` Service (`10.96.0.1`)

If **metrics-server** exits with a **panic** mentioning:

`Get "https://10.96.0.1:443/...": dial tcp 10.96.0.1:443: connect: no route to host`

the failure is **not** kubelet TLS. The pod has **no working route** to the **default Kubernetes Service** (in-cluster API VIP). With **Cilium kube-proxy replacement**, fix the dataplane so **pods** can reach the **Service CIDR**, and confirm **`k8sServiceHost`** / **`k8sServicePort`** match an API address reachable from **every** node (§5). Check **host firewalls** between pod CIDR, service CIDR, and **TCP 6443** on the control plane.

Quick check from a throwaway pod:

```bash
kubectl get svc kubernetes -n default
kubectl run -n default netcheck --rm -it --restart=Never --image=curlimages/curl:latest -- \
  curl -k -sS -m 5 -o /dev/null -w "%{http_code}\n" https://10.96.0.1/healthz
```

**kubectl:** options like `--kubelet-insecure-tls` belong in the **metrics-server** container **`args`** (edit the Deployment YAML), not as flags on `kubectl edit`.

**Narrow workaround:** `hostNetwork: true` on the metrics-server Deployment can sometimes work around a broken pod→ClusterIP path; prefer fixing Cilium/routing so all workloads reach Services.

---

## 7. Hubble Relay (stay healthy)

Keep **Cilium + Hubble** values **in `k0s`’s Cilium Helm stanza** (see [`k0s.yaml.example`](k0s.yaml.example) or [`k0s.production.example.yaml`](k0s.production.example.yaml)) so upgrades do not silently strip Hubble. That file pins **`cluster.name`**, **`hubble.relay.peerService.internalTrafficPolicy: Cluster`**, and **`hubble.tls.auto`** (`method: helm`) — all of which matter for a stable **Hubble Relay**.

### TLS / `cluster-name` mismatch

Hubble Relay verifies TLS using `hubble-peer.<cluster-name>.hubble-grpc.cilium.io`. The agents’ certs must match the same **`cluster-name`** as `cilium-config` and `hubble-relay-config`.

**Explicit `cluster.name` in Helm user values:** Keep `cluster.name` **under the Cilium Helm `values`** in k0s (not only relying on chart defaults). We have seen **`hubble-server-certs`** minted with **`*.local.hubble-grpc.cilium.io`** while `cilium-config` still had **`cluster-name: default`** — Relay then fails TLS until secrets are recreated with the correct name. After fixing, confirm with:

```bash
helm get values cilium -n kube-system | head -20
kubectl get secret -n kube-system hubble-server-certs -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -ext subjectAltName
```

**Helm stuck in `pending-rollback`:** If `helm status` shows a failed revision and **pending-rollback**, finish it before upgrading: `helm history cilium -n kube-system` then `helm rollback cilium <last-deployed-revision> -n kube-system --wait`.

**Force-correct certs (cluster already on `default`):**

```bash
kubectl -n kube-system delete secret hubble-server-certs hubble-relay-client-certs
helm upgrade cilium cilium/cilium -n kube-system --version 1.19.2 --reuse-values \
  --set cluster.name=default --set hubble.relay.peerService.internalTrafficPolicy=Cluster --wait
kubectl -n kube-system rollout restart ds/cilium deploy/hubble-relay
kubectl -n kube-system patch svc hubble-peer -p '{"spec":{"internalTrafficPolicy":"Cluster"}}'
```

(Adjust `--version` to your chart pin.)

```bash
kubectl -n kube-system get cm cilium-config -o jsonpath='{.data.cluster-name}{"\n"}'
kubectl -n kube-system get cm hubble-relay-config -o yaml | head -5
```

If logs show **`x509: certificate is valid for *.local... not hubble-peer.default...`**, either set **`cluster.name`** in Helm to match the certs you minted, or (recommended for **`default`**) **delete Hubble TLS Secrets** in `kube-system`, **re-run the Cilium install** (`helm upgrade` / k0s stack apply) so `method: helm` recreates secrets, then:

```bash
kubectl -n kube-system rollout restart ds/cilium
kubectl -n kube-system rollout restart deploy/hubble-relay
```

### Relay cannot open peer notify (Cilium 1.19.x)

If Relay logs **`Failed to create peer notify client`** with **`operation not permitted`** dialing the **ClusterIP**, set the peer Service to **Cluster** policy (Helm: `hubble.relay.peerService.internalTrafficPolicy: Cluster`; or one-shot `kubectl patch svc hubble-peer -n kube-system -p '{"spec":{"internalTrafficPolicy":"Cluster"}}'`). Rare cases need a **one-time** `cleanBPFState: true` Cilium cycle — see [cilium#44891](https://github.com/cilium/cilium/issues/44891).

**Always capture the full line** (Relay truncates in some UIs):

```bash
kubectl -n kube-system logs deploy/hubble-relay --tail=50 | grep -E 'error=|x509|peer notify|Received peer'
```

Interpretation:

| `error=` snippet | Action |
|------------------|--------|
| `x509` / `certificate` / `*.local.hubble-grpc` vs `hubble-peer.default` | **TLS / cluster-name drift** — regenerate secrets (below). |
| `operation not permitted` dialing ClusterIP | **`internalTrafficPolicy: Cluster`** on `hubble-peer` and/or BPF note in §7. |
| `connection refused` / `timeout` | Agents not listening, network, or wrong `hubble-peer` endpoints. |

### Regenerate Hubble TLS secrets (after changing `cluster.name` or fixing a mismatch)

`rollout restart` **does not** re-issue Helm minted certs. **`hubble.tls.auto.method: helm`** creates or updates secrets when **Cilium’s Helm release** is upgraded/reconciled **after** old secrets are removed.

1. **Confirm intended cluster name** (must match Helm `cluster.name`):

   ```bash
   kubectl -n kube-system get cm cilium-config -o jsonpath='{.data.cluster-name}{"\n"}'
   ```

2. **Confirm `hubble-peer` traffic policy** (should be `Cluster` on 1.19.x):

   ```bash
   kubectl -n kube-system get svc hubble-peer -o jsonpath='{.spec.internalTrafficPolicy}{"\n"}'
   kubectl patch svc hubble-peer -n kube-system -p '{"spec":{"internalTrafficPolicy":"Cluster"}}'   # if not Cluster
   ```

3. **List and remove Hubble TLS secrets** (names can vary slightly by chart version; list first):

   ```bash
   kubectl -n kube-system get secrets | grep -i hubble
   ```

   Typical **Cilium 1.19** chart materials include **`hubble-server-certs`** and **`hubble-relay-client-certs`**. Delete those (and any other `hubble-*-certs` TLS secrets); **do not** delete unrelated **`cilium-*`** secrets unless you know they are only for Hubble.

   ```bash
   kubectl -n kube-system delete secret hubble-server-certs hubble-relay-client-certs --ignore-not-found
   ```

4. **Re-run the Cilium Helm install** so templates recreate secrets. With **k0s extensions**, that means bringing the release in sync again — for example **restart k0s on a controller** after saving `/etc/k0s/k0s.yaml`, or run the equivalent **Helm upgrade** yourself against `kube-system` using the same `values` block as in ClusterConfig. Until Helm runs again, pods may stay broken.

5. **Roll workloads** to load new mounts:

   ```bash
   kubectl -n kube-system rollout restart ds/cilium
   kubectl -n kube-system rollout restart deploy/hubble-relay
   ```

6. **Optional:** inspect that a server cert SAN matches `cluster-name`:

   ```bash
   kubectl -n kube-system get secret hubble-server-certs -o jsonpath='{.data.tls\.crt}' | base64 -d \
     | openssl x509 -noout -ext subjectAltName 2>/dev/null || true
   ```

   You should see a pattern like **`*.<cluster-name>.hubble-grpc.cilium.io`** aligned with `cilium-config` **`cluster-name`**.

### Hubble UI (same chart as Cilium)

Enable the web UI in the **same** `cilium/cilium` Helm values — **not** the “standalone UI only” snippet from older docs:

```yaml
hubble:
  ui:
    enabled: true
```

Keep **`hubble.ui.standalone.enabled: false`** (default). **Standalone** mode is for installing **only** the UI against a cluster that already has Cilium/Relay from elsewhere; it needs a **`certsVolume`** with relay client TLS material. In a normal k0s + embedded Cilium install, the chart wires UI → Relay and uses the same TLS setup as Relay.

Expose the UI with **`kubectl port-forward -n kube-system svc/hubble-ui 12000:80`**, **`NodePort`** (`hubble.ui.service.type`), or chart **`hubble.ui.ingress`** (e.g. Traefik `ingressClassName`). The Service is **`hubble-ui`** in **`kube-system`** by default. On **production** GitOps, Traefik ingress for **`hubble.mgmt.wsh.no`** lives in [`clusters/production/apps/hubble-ui-ingress.yaml`](../../clusters/production/apps/hubble-ui-ingress.yaml) (Ingress must be in **`kube-system`** with the backend Service).

### Verify

```bash
cilium status
kubectl -n kube-system logs deploy/hubble-relay --tail=20 | grep -i 'peer\|error\|Received'
kubectl -n kube-system get svc hubble-ui
```

---

## 8. After CNI: CSI (Ceph) and GitOps

- **Ceph CSI** is **separate** from this guide: install the driver, pools, secrets, and **`StorageClass`** after pod networking is stable — see the overview in [`README.md`](README.md) §5–7.
- **Flux** can own **Cilium long-term** (HelmRelease) once you are comfortable repeating bootstrap; first cluster install is often **plain Helm** or k0s extensions, then migrate to GitOps if you want.

---

## 9. Third-party articles

Blog posts (e.g. [OneUptime – Configure Cilium on k0s](https://oneuptime.com/blog/post/2026-03-13-configure-cilium-k0s/view)) are useful for **workflow**, but often use **`127.0.0.1`** as `k8sServiceHost` (suitable only on a **single** controller where that matches reality) and may include **misleading CoreDNS commentary**. Prefer **this file** + **k0s/Cilium versioned docs** for values you actually apply.

---

## Checklist

- [ ] `podCIDR` / `serviceCIDR` chosen; no overlap with LAN or Ceph  
- [ ] `provider: custom`; Cilium install procedure ready; versions pinned  
- [ ] `kubeProxy` / `kubeProxyReplacement` aligned for your k0s + Cilium pair  
- [ ] **`k8sServiceHost`** = reachable **control-plane** address from **all** nodes  
- [ ] Firewalls: workers → **6443**, **8132**; pod/service ranges allowed as needed  
- [ ] **CoreDNS** left enabled  
- [ ] Cilium **Ready**; basic pod + **DNS** check passed  
- [ ] Then: Ceph CSI, then workloads / Flux  
- [ ] **Hubble:** `cluster.name` aligned with Hubble TLS; `peerService.internalTrafficPolicy: Cluster`; Relay **Ready** (`cilium status`)  
