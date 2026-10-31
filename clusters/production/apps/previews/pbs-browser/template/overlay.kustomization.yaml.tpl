apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: pbs-browser-preview-pr-__PR__

resources:
- ../base
- namespace.yaml

# `labels` (vs deprecated `commonLabels`) with includeSelectors: false — identification only; keeps
# the PR label out of selectors so it can't break the netpol-baseline same-namespace matching.
labels:
- pairs:
    pbs-browser.wsh.no/pr: "__PR__"
  includeSelectors: false
  includeTemplates: true

# __IMAGE_TAG__ / __IMAGE_DIGEST__ carry the MANIFEST ARTIFACT's tag (pr-<N>) and digest, not the
# image's: the artifact pins the image itself. The digest pins the deploy to exactly what this PR
# run pushed; the tag is kept alongside for readability (`flux get sources oci`).
patches:
- target:
    kind: OCIRepository
    name: pbs-browser
  patch: |-
    - op: replace
      path: /spec/ref
      value:
        tag: "__IMAGE_TAG__"
        digest: "__IMAGE_DIGEST__"
- target:
    kind: Kustomization
    name: pbs-browser
  patch: |-
    - op: replace
      path: /spec/targetNamespace
      value: pbs-browser-preview-pr-__PR__
    - op: replace
      path: /spec/postBuild/substitute/APP_HOST
      value: __HOST__
