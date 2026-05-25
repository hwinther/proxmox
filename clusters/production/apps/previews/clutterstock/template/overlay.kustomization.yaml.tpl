apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: clutterstock-pr-__PR__

resources:
- ../base
- namespace.yaml

# `labels` (vs deprecated `commonLabels`) with includeSelectors: false avoids leaking the PR label
# into NetworkPolicy podSelectors that target peers in other namespaces (kube-dns, redis, etc.).
labels:
- pairs:
    clutterstock.wsh.no/pr: "__PR__"
  includeSelectors: false
  includeTemplates: true

# Image digests pin the deploy to exactly the artifacts that just passed e2e + grype. The tag
# (newTag) is kept alongside the digest so `kubectl get deploy -o yaml | grep image:` is readable.
images:
- name: ghcr.io/hwinther/clutterstock/api
  newTag: "__IMAGE_API_TAG__"
  digest: "__IMAGE_API_DIGEST__"
- name: ghcr.io/hwinther/clutterstock/frontend
  newTag: "__IMAGE_FRONTEND_TAG__"
  digest: "__IMAGE_FRONTEND_DIGEST__"
- name: ghcr.io/hwinther/clutterstock/migrator
  newTag: "__IMAGE_MIGRATOR_TAG__"
  digest: "__IMAGE_MIGRATOR_DIGEST__"

patches:
- target:
    kind: Deployment
    name: clutterstock-api
  patch: |-
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: clutterstock-api
    spec:
      template:
        spec:
          initContainers:
          - name: migrator
            env:
            - name: PG_DB
              value: __DB_NAME__
          containers:
          - name: clutterstock-api
            env:
            - name: PG_DB
              value: __DB_NAME__
            - name: OTEL_RESOURCE_ATTRIBUTES
              value: "service.namespace=clutterstock-pr-__PR__,deployment.environment=preview"
- target:
    kind: Deployment
    name: clutterstock-frontend
  patch: |-
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: clutterstock-frontend
    spec:
      template:
        spec:
          containers:
          - name: clutterstock-frontend
            env:
            - name: PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
              value: "https://__HOST__/v1/traces"
            - name: PUBLIC_ORIGIN
              value: "https://__HOST__"
- target:
    kind: Ingress
    name: clutterstock
  patch: |-
    - op: replace
      path: /spec/rules/0/host
      value: __HOST__
