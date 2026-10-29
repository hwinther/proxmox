apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: clutterstock-preview-pr-__PR__

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

# __IMAGE_TAG__ / __IMAGE_DIGEST__ carry the MANIFEST ARTIFACT's tag (pr-<N>) and digest, not an
# image's: the artifact pins the api, migrator and frontend images itself. The digest pins the
# deploy to exactly what this PR run pushed after e2e + grype; the tag is kept alongside for
# readability (`flux get sources oci`).
patches:
- target:
    kind: OCIRepository
    name: clutterstock
  patch: |-
    - op: replace
      path: /spec/ref
      value:
        tag: "__IMAGE_TAG__"
        digest: "__IMAGE_DIGEST__"
- target:
    kind: Kustomization
    name: clutterstock
  patch: |-
    - op: replace
      path: /spec/targetNamespace
      value: clutterstock-preview-pr-__PR__
    - op: replace
      path: /spec/postBuild/substitute/APP_HOST
      value: __HOST__
    - op: replace
      path: /spec/postBuild/substitute/PG_DB
      value: __DB_NAME__
