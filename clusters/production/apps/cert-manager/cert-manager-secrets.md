# cert-manager credentials (production)

TLS for cluster workloads uses **cert-manager** in namespace **`cert-manager`**. This directory ships a **`ClusterIssuer`** `letsencrypt-dns` that completes **ACME DNS-01** using **RFC2136** (TSIG), the same mechanism as nginx DNS challenges and Proxmox ACME when pointed at BIND / PowerDNS / similar.

## 1. CA scope (what this issuer is for)

- **Public Let’s Encrypt certificates** for DNS names under **`wsh.no`** that resolve publicly and pass HTTP-01/DNS-01 validation rules (no internal-only TLDs such as `*.svc.cluster.local`).
- **Private / internal-only names** (for example pure in-cluster DNS) are **out of scope** for this `ClusterIssuer`; use a separate CA issuer or another secret workflow if you need those SANs.

The `ClusterIssuer` solver is limited to the **`wsh.no`** zone via `spec.acme.solvers[].selector.dnsZones`.

## 2. RFC2136 TSIG secret (required before certificates issue)

Create a **TSIG key** on your authoritative DNS server (same style as for nginx or Proxmox), then store the shared secret in Kubernetes.

Example (key name and secret must match [`clusterissuer-letsencrypt-dns.yaml`](clusterissuer-letsencrypt-dns.yaml)):

```bash
# Put the TSIG shared secret bytes in a local file using the format cert-manager expects for your algorithm
# (see upstream RFC2136 docs), then:
kubectl create secret generic rfc2136-tsig-wsh-no \
  --namespace cert-manager \
  --from-file=tsig-secret=./tsig-secret.key
```

cert-manager expects the key referenced by **`tsigSecretSecretRef.key`** (`tsig-secret` here) to hold the secret material in the format your DNS software documents (commonly raw key bytes or base64; match what cert-manager’s RFC2136 solver expects for your algorithm — see [cert-manager RFC2136](https://cert-manager.io/docs/configuration/acme/dns01/rfc2136/)).

## 3. Edit the ClusterIssuer to match your environment

1. **`spec.acme.email`** — Let’s Encrypt account contact; must be deliverable mail for expiry/security notices.
2. **`spec.acme.solvers[].dns01.rfc2136.nameserver`** — Address of the DNS server that accepts **signed updates** for `wsh.no` (often the same host you configured for nginx RFC2136). Include port if not `53`, e.g. `10.0.0.1:53`.
3. **`tsigKeyName`** — Exact TSIG key name on the server (trailing dot is conventional for absolute names).
4. **`tsigAlgorithm`** — Must match the server (`HMACSHA256`, `HMACSHA512`, etc.).

After changing the issuer or secret, watch challenges:

```bash
kubectl get clusterissuer letsencrypt-dns -o wide
kubectl get certificate -A
kubectl describe challenge -n rabbitmq-production
```

Staging directory (for dry-runs): `https://acme-staging-v02.api.letsencrypt.org/directory` — use a **different** `metadata.name` / `privateKeySecretRef` if you add a staging issuer so account keys do not collide.

## 4. RabbitMQ bootstrap note

`RabbitmqCluster` references `Secret` **`rabbitmq-tls`** before cert-manager has written it. Until **`Certificate` `rabbitmq-tls`** is **Ready**, RabbitMQ pods may stay in **ContainerCreating** (missing volume). Apply the TSIG secret and correct **`nameserver` / `tsigKeyName`** in [`clusterissuer-letsencrypt-dns.yaml`](clusterissuer-letsencrypt-dns.yaml) **before** or immediately after merging so the first issuance succeeds quickly.

## 5. Verify RabbitMQ TLS after issuance

Once `Certificate` `rabbitmq-tls` is **Ready** and the `Secret` `rabbitmq-tls` exists in `rabbitmq-production`:

```bash
kubectl get certificate rabbitmq-tls -n rabbitmq-production
kubectl get secret rabbitmq-tls -n rabbitmq-production -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -subject -dates -ext subjectAltName
```

From a debug pod with `openssl` (or any host that can reach the broker on **5671**):

```bash
openssl s_client -connect rabbitmq.rabbitmq-production.svc.cluster.local:5671 \
  -servername rabbitmq.wsh.no -brief </dev/null
```

The certificate is issued for **public** `wsh.no` names; clients must use a **hostname present in SAN** (for example `rabbitmq.wsh.no` as TLS server name) when they verify the chain. Connecting with only `*.svc.cluster.local` as the verify hostname will **not** match a Let’s Encrypt certificate.
