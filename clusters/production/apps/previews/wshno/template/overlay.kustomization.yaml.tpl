apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: wshno-preview-pr-__PR__

resources:
- ../base
- namespace.yaml

# `labels` (vs deprecated `commonLabels`) with includeSelectors: false — identification only; keeps
# the PR label out of selectors so it can't break the netpol-baseline same-namespace matching.
labels:
- pairs:
    wshno.wsh.no/pr: "__PR__"
  includeSelectors: false
  includeTemplates: true

# __IMAGE_TAG__ / __IMAGE_DIGEST__ carry the MANIFEST ARTIFACT's tag (pr-<N>) and digest, not the
# image's: the artifact pins the image itself. The digest pins the deploy to exactly what this PR
# run pushed; the tag is kept alongside for readability (`flux get sources oci`).
patches:
- target:
    kind: OCIRepository
    name: wshno
  patch: |-
    - op: replace
      path: /spec/ref
      value:
        tag: "__IMAGE_TAG__"
        digest: "__IMAGE_DIGEST__"
- target:
    kind: Kustomization
    name: wshno
  patch: |-
    - op: replace
      path: /spec/targetNamespace
      value: wshno-preview-pr-__PR__
- target:
    kind: Ingress
    name: wshno
  patch: |-
    - op: replace
      path: /spec/rules/0/host
      value: __HOST__
