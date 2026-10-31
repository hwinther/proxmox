apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: ddnsadmin-preview-pr-__PR__

resources:
- ../base
- namespace.yaml

# `labels` (vs deprecated `commonLabels`) with includeSelectors: false avoids leaking the PR label
# into NetworkPolicy podSelectors that target peers in other namespaces (kube-dns, traefik).
labels:
- pairs:
    ddnsadmin.wsh.no/pr: "__PR__"
  includeSelectors: false
  includeTemplates: true

# __IMAGE_TAG__ / __IMAGE_DIGEST__ carry the MANIFEST ARTIFACT's tag (pr-<N>) and digest, not the
# image's: the artifact pins the image itself. The digest pins the deploy to exactly what this PR
# run pushed; the tag is kept alongside for readability (`flux get sources oci`). APP_HOST sets the
# Ingress host and WEB_PREFIX inside the artifact.
patches:
- target:
    kind: OCIRepository
    name: ddnsadmin
  patch: |-
    - op: replace
      path: /spec/ref
      value:
        tag: "__IMAGE_TAG__"
        digest: "__IMAGE_DIGEST__"
- target:
    kind: Kustomization
    name: ddnsadmin
  patch: |-
    - op: replace
      path: /spec/targetNamespace
      value: ddnsadmin-preview-pr-__PR__
    - op: replace
      path: /spec/postBuild/substitute/APP_HOST
      value: __HOST__
