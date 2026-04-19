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

Management plugin listens on **15672** inside the cluster (no public Ingress is defined here).

## 3. Order of operations

1. Flux applies operators + `RabbitmqCluster` → wait until pods are Ready.
2. Create **`test-api-rabbitmq-credentials`** then ensure `User`/`Permission`/`Vhost` objects reconcile.
3. Create **`test-api-rabbitmq`** in `test-test` before rolling **`test-api`** if it uses `secretKeyRef` (missing keys block pod startup).

## 4. Upgrading the messaging topology operator manifest

`messaging-topology-operator-no-namespace.yaml` is the upstream **`messaging-topology-operator.yaml`** release asset with the **first `Namespace/rabbitmq-system` document removed**, so it can live in the same Kustomize build as **`cluster-operator.yml`** (which already defines that namespace). When bumping the topology operator version, re-download the release YAML, strip that first document, and replace the file.
