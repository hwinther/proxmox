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

**Authelia:** the Ingress uses the same **forward-auth** Middleware as Headlamp (`headlamp-production-authelia-forwardauth`). Only LDAP users in group **`k8s-admins`** pass Authelia ([`../authelia-production/authelia-helmrelease.yaml`](../authelia-production/authelia-helmrelease.yaml) `access_control`). You still sign in to the **RabbitMQ** UI with credentials from Secret **`rabbitmq-default-user`** (or another management user you created) — Authelia only guards the edge URL.

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

Public **Ingress** for the management UI is **`rabbitmq.mgmt.wsh.no`** (Traefik `web` entrypoint → Service **`rabbitmq`** port **15672**). Direct TLS to the broker on **`rabbitmq.mgmt.wsh.no`** (port **15671**) is separate and uses the **`rabbitmq-tls`** Secret on the nodes.

