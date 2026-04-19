# RabbitMQ credentials (Cluster + Topology operators)

Passwords and import secrets live only in **Kubernetes Secrets** (not in this repo).

The broker Service is **`rabbitmq.rabbitmq-production.svc.cluster.local`** (port **5672**). Clients in other namespaces must use the full DNS name.

**Virtual hosts:** the cluster defines two shared vhosts (not per-app): **`prod`** for production workloads and **`test`** for test / non-prod workloads ([`topology-vhost-prod.yaml`](topology-vhost-prod.yaml), [`topology-vhost-test.yaml`](topology-vhost-test.yaml)). The default **`/`** vhost still exists but is unused by these manifests. Add **`User`** + **`Permission`** resources for each app or shared service account on the appropriate vhost.

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

### Clutterstock (`clutterstock-test` / `clutterstock-production`)

Broker users **`clutterstock-test`** and **`clutterstock-prod`** map to shared vhosts **`test`** and **`prod`** ([`topology-user-clutterstock-test.yaml`](topology-user-clutterstock-test.yaml), [`topology-permission-clutterstock-test.yaml`](topology-permission-clutterstock-test.yaml), prod equivalents). The API Deployments read **`clutterstock-test-rabbitmq`** / **`clutterstock-production-rabbitmq`** in their namespaces (`RabbitMq__*` env vars).

Create import secrets in **`rabbitmq-production`** first, then app secrets (same password per user):

```bash
PW_TEST="$(openssl rand -base64 32 | tr -d '\n')"
PW_PROD="$(openssl rand -base64 32 | tr -d '\n')"

kubectl create secret generic clutterstock-test-rabbitmq-credentials \
  --namespace rabbitmq-production \
  --from-literal=username=clutterstock-test \
  --from-literal=password="$PW_TEST"

kubectl create secret generic clutterstock-test-rabbitmq \
  --namespace clutterstock-test \
  --from-literal=username=clutterstock-test \
  --from-literal=password="$PW_TEST"

kubectl create secret generic clutterstock-prod-rabbitmq-credentials \
  --namespace rabbitmq-production \
  --from-literal=username=clutterstock-prod \
  --from-literal=password="$PW_PROD"

kubectl create secret generic clutterstock-production-rabbitmq \
  --namespace clutterstock-production \
  --from-literal=username=clutterstock-prod \
  --from-literal=password="$PW_PROD"
```

## 2. Cluster admin UI / default user

The Cluster Operator creates **`rabbitmq-default-user`** (name pattern `rabbitmq-default-user`) in `rabbitmq-production` with connection details. Use:

```bash
kubectl get secret rabbitmq-default-user -n rabbitmq-production -o yaml
```

Management plugin listens on **15672** (HTTP) inside the cluster. Traefik + Homepage use **`https://rabbitmq.mgmt.wsh.no`** via [`rabbitmq-management-ingress.yaml`](rabbitmq-management-ingress.yaml) (ensure DNS / edge proxy match other `*.mgmt.wsh.no` names). Traefik uses **hostNetwork** on k0s: reachability also needs [`cilium-cluster-nodes-to-rabbitmq-management.yaml`](cilium-cluster-nodes-to-rabbitmq-management.yaml) (see [`../traefik/README.md`](../traefik/README.md)).

**Authelia (OIDC SSO):** the management UI uses **OAuth 2 / OIDC** against Authelia at **`https://auth.wsh.no`** (public client **`rabbitmq-management`**, PKCE). Only LDAP users in **`k8s-admins`** may authorize that client ([`../authelia-production/authelia-helmrelease.yaml`](../authelia-production/authelia-helmrelease.yaml) `identity_providers.oidc.authorization_policies.rabbitmq-management-admins`). Key configuration notes:

- **JWT access tokens:** the client must set **`access_token_signed_response_alg: RS256`** and **`access_token_signed_response_key_id`** so Authelia issues signed JWT access tokens (not opaque). Without this, `auth_backend_oauth2` cannot parse the token.
- **Audience:** must include **`rabbitmq`** (matches `auth_oauth2.resource_server_id`).
- **Scopes:** the client requests only standard OIDC scopes (`openid`, `profile`, `email`, `groups`). RabbitMQ permissions are **not** embedded as scope strings — Authelia's Helm chart cannot register custom scopes with dots/colons in their names (key flattening breaks them).
- **Permissions via group-based scope aliases:** `auth_oauth2.additional_scopes_key = groups` reads the JWT `groups` claim as extra scopes. An `advancedConfig` scope alias maps `k8s-admins` → `rabbitmq.tag:administrator`, `rabbitmq.read:*/*`, `rabbitmq.write:*/*`, `rabbitmq.configure:*/*` (Erlang term format; cuttlefish cannot express hyphens in alias keys).
- **Username resolution:** `auth_oauth2.preferred_username_claims` lists `sub` first (Authelia's internal UUID), then `email`, `preferred_username`, `name`. If none are found, the plugin falls back to `client_id` (`rabbitmq-management`) and login fails with "invalid credentials".
- **TLS wildcard certs:** `auth_oauth2.https.hostname_verification = wildcard` is required because Traefik serves `*.wsh.no` for `auth.wsh.no`; Erlang's default strict hostname check rejects wildcards.
- **`rabbitmq-default-user`** remains for AMQP and recovery; **`management.oauth_disable_basic_auth = true`** hides the legacy management login when OAuth is enabled ([`rabbitmq-cluster.yaml`](rabbitmq-cluster.yaml)).

## 3. Order of operations

1. Flux applies operators + `RabbitmqCluster` → wait until pods are Ready.
2. Create **`test-api-rabbitmq-credentials`** then ensure `User`/`Permission`/`Vhost` objects reconcile (sample app **`test-api`** uses vhost **`test`**).
3. Create **`test-api-rabbitmq`** in `test-test` before rolling **`test-api`** if it uses `secretKeyRef` (missing keys block pod startup).
4. For Clutterstock: create the four Secrets above, then roll **`clutterstock-api`** in **`clutterstock-test`** / **`clutterstock-production`** once `User`/`Permission` resources are Ready.

## 4. Upgrading the messaging topology operator manifest

`messaging-topology-operator-no-namespace.yaml` is the upstream **`messaging-topology-operator.yaml`** release asset with the **first `Namespace/rabbitmq-system` document removed**, so it can live in the same Kustomize build as **`cluster-operator.yml`** (which already defines that namespace). When bumping the topology operator version, re-download the release YAML, strip that first document, and replace the file.

## 5. TLS (AMQPS / management)

The cluster references **`spec.tls.secretName: rabbitmq-tls`**, populated by cert-manager **`Certificate`** [`certificate-rabbitmq-tls.yaml`](certificate-rabbitmq-tls.yaml) using **`ClusterIssuer`** `letsencrypt-dns` (RFC2136). Create the TSIG secret and fix the issuer nameserver/key name first — see [`../cert-manager/cert-manager-secrets.md`](../cert-manager/cert-manager-secrets.md).

- **AMQPS** listens on **5671** when TLS is enabled (plain AMQP remains on **5672** unless you change listener config separately).
- The issued certificate covers **`rabbitmq.wsh.no`** and **`rabbitmq.mgmt.wsh.no`**. Clients that verify TLS must use a **hostname present in the cert** (for example **`rabbitmq.wsh.no` as the server name**), not only `rabbitmq.rabbitmq-production.svc.cluster.local`, or hostname verification will fail against Let's Encrypt.
- After Flux applies changes, confirm the cert is **Ready**, then run the checks in cert-manager-secrets.md §5 (OpenSSL).

Public **Ingress** for the management UI is **`https://rabbitmq.mgmt.wsh.no`** (Traefik `web` entrypoint → Service **`rabbitmq`** port **15672**). Direct TLS to the broker on **`rabbitmq.mgmt.wsh.no`** (port **15671**) is separate and uses the **`rabbitmq-tls`** Secret on the nodes.

## 6. Prometheus metrics and MQTT

The cluster enables **`rabbitmq_prometheus`** and **`rabbitmq_mqtt`** ([`rabbitmq-cluster.yaml`](rabbitmq-cluster.yaml)). With **`spec.tls`**, the operator exposes metrics on **HTTPS port 15691** (Service port name **`prometheus-tls`**); kube-prometheus-stack includes a **PodMonitor** so each replica is scraped ([`../observability/kube-prometheus-stack-helmrelease.yaml`](../observability/kube-prometheus-stack-helmrelease.yaml)). **`NetworkPolicy`** allows **`observability-production`** → **15691** ([`networkpolicy-rabbitmq.yaml`](networkpolicy-rabbitmq.yaml)).

**MQTT:** plain **1883** and TLS **8883** are added on the **`rabbitmq`** Service when the plugin is enabled. The NetworkPolicy does **not** allow them from other namespaces yet; add an ingress rule (and Cilium if you use host-network paths) when **edge-sdr** or other workloads need to connect.
