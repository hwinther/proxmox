# RabbitMQ credentials (Cluster + Topology operators)

Passwords and import secrets live only in **Kubernetes Secrets** (not in this repo).

The broker Service is **`rabbitmq.rabbitmq-production.svc.cluster.local`** (port **5672**). Clients in other namespaces must use the full DNS name.

## 1. Bootstrap: topology import secret + app env secret

Create the **import** secret in `rabbitmq-production` first (Messaging Topology Operator reads it for `User` `test-api`). Use the same username/password values for the app Secret in `test-test`.

Example (pick a strong password; `test-api` is the RabbitMQ username):

```bash
PW="$(openssl rand -base64 32 | tr -d '\n')"

kubectl create secret generic test-api-rabbitmq-credentials \
  --namespace rabbitmq-production \
  --from-literal=username=test-api \
  --from-literal=password="$PW"

kubectl create secret generic test-api-rabbitmq \
  --namespace test-test \
  --from-literal=username=test-api \
  --from-literal=password="$PW"
```

If the `User` object already reconciled and you rotated the import secret, add a label on the `User` to force reconcile (see [upstream note](https://github.com/rabbitmq/messaging-topology-operator/blob/main/docs/examples/users/userPreDefinedCreds.yaml)).

## 2. Cluster admin UI / default user

The Cluster Operator creates **`rabbitmq-default-user`** (name pattern `rabbitmq-default-user`) in `rabbitmq-production` with connection details. Use:

```bash
kubectl get secret rabbitmq-default-user -n rabbitmq-production -o yaml
```

Management plugin listens on **15672** (HTTP) inside the cluster. Traefik + Homepage use **`https://rabbitmq.mgmt.wsh.no`** via [`rabbitmq-management-ingress.yaml`](rabbitmq-management-ingress.yaml) (ensure DNS / edge proxy match other `*.mgmt.wsh.no` names). Traefik uses **hostNetwork** on k0s: reachability also needs [`cilium-cluster-nodes-to-rabbitmq-management.yaml`](cilium-cluster-nodes-to-rabbitmq-management.yaml) (see [`../traefik/README.md`](../traefik/README.md)).

**Authelia (OIDC SSO):** the management UI uses **OAuth 2 / OIDC** against Authelia at **`https://auth.wsh.no`** (public client **`rabbitmq-management`**, PKCE). The browser is redirected to Authelia; after login, RabbitMQ validates the **JWT access token** (JWKS from the issuer). Only LDAP users in **`k8s-admins`** may complete the OIDC authorization for that client ([`../authelia-production/authelia-helmrelease.yaml`](../authelia-production/authelia-helmrelease.yaml) `identity_providers.oidc.authorization_policies.rabbitmq-management-admins`). The client only requests **`openid` `profile` `email` `groups`** (Authelia’s OIDC client scope allow-list). Broker-side, **`auth_oauth2.additional_scopes_key = groups`** plus **`rabbitmq.advancedConfig`** `scope_aliases` map LDAP group **`k8s-admins`** to RabbitMQ scopes on **4.0.x** (cuttlefish `auth_oauth2.scope_aliases.*` is not available until newer broker versions). Redirect URIs include **`https://rabbitmq.mgmt.wsh.no/js/oidc-oauth/login-callback.html`**. **`rabbitmq-default-user`** remains for AMQP and for recovery if OIDC is misconfigured; **`management.oauth_disable_basic_auth = true`** hides the old management login form when OAuth is enabled ([`rabbitmq-cluster.yaml`](rabbitmq-cluster.yaml)).

## 3. Order of operations

1. Flux applies operators + `RabbitmqCluster` → wait until pods are Ready.
2. Create **`test-api-rabbitmq-credentials`** then ensure `User`/`Permission`/`Vhost` objects reconcile.
3. Create **`test-api-rabbitmq`** in `test-test` before rolling **`test-api`** if it uses `secretKeyRef` (missing keys block pod startup).

## 4. Upgrading the messaging topology operator manifest

`messaging-topology-operator-no-namespace.yaml` is the upstream **`messaging-topology-operator.yaml`** release asset with the **first `Namespace/rabbitmq-system` document removed**, so it can live in the same Kustomize build as **`cluster-operator.yml`** (which already defines that namespace). When bumping the topology operator version, re-download the release YAML, strip that first document, and replace the file.

## 5. TLS (AMQPS / management)

The cluster references **`spec.tls.secretName: rabbitmq-tls`**, populated by cert-manager **`Certificate`** [`certificate-rabbitmq-tls.yaml`](certificate-rabbitmq-tls.yaml) using **`ClusterIssuer`** `letsencrypt-dns` (RFC2136). Create the TSIG secret and fix the issuer nameserver/key name first — see [`../cert-manager/cert-manager-secrets.md`](../cert-manager/cert-manager-secrets.md).

- **AMQPS** listens on **5671** when TLS is enabled (plain AMQP remains on **5672** unless you change listener config separately).
- The issued certificate covers **`rabbitmq.wsh.no`** and **`rabbitmq.mgmt.wsh.no`**. Clients that verify TLS must use a **hostname present in the cert** (for example **`rabbitmq.wsh.no` as the server name**), not only `rabbitmq.rabbitmq-production.svc.cluster.local`, or hostname verification will fail against Let’s Encrypt.
- After Flux applies changes, confirm the cert is **Ready**, then run the checks in cert-manager-secrets.md §5 (OpenSSL).

Public **Ingress** for the management UI is **`https://rabbitmq.mgmt.wsh.no`** (Traefik `web` entrypoint → Service **`rabbitmq`** port **15672**). Direct TLS to the broker on **`rabbitmq.mgmt.wsh.no`** (port **15671**) is separate and uses the **`rabbitmq-tls`** Secret on the nodes.

## 6. Prometheus metrics and MQTT

The cluster enables **`rabbitmq_prometheus`** and **`rabbitmq_mqtt`** ([`rabbitmq-cluster.yaml`](rabbitmq-cluster.yaml)). With **`spec.tls`**, the operator exposes metrics on **HTTPS port 15691** (Service port name **`prometheus-tls`**); kube-prometheus-stack includes a **PodMonitor** so each replica is scraped ([`../observability/kube-prometheus-stack-helmrelease.yaml`](../observability/kube-prometheus-stack-helmrelease.yaml)). **`NetworkPolicy`** allows **`observability-production`** → **15691** ([`networkpolicy-rabbitmq.yaml`](networkpolicy-rabbitmq.yaml)).

**MQTT:** plain **1883** and TLS **8883** are added on the **`rabbitmq`** Service when the plugin is enabled. The NetworkPolicy does **not** allow them from other namespaces yet; add an ingress rule (and Cilium if you use host-network paths) when **edge-sdr** or other workloads need to connect.
