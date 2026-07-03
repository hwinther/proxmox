apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: skylens-preview-pr-__PR__

resources:
- ../base
- namespace.yaml

# `labels` (vs deprecated `commonLabels`) with includeSelectors: false — identification only; keeps
# the PR label out of selectors so it can't break the netpol-baseline same-namespace matching.
labels:
- pairs:
    skylens.wsh.no/pr: "__PR__"
  includeSelectors: false
  includeTemplates: true

# Single PUBLIC image: digest pins the deploy to exactly the artifact the PR build pushed; the tag
# (newTag) is kept alongside so `kubectl get deploy -o yaml | grep image:` stays readable.
images:
- name: ghcr.io/hwinther/skylens/api
  newTag: "__IMAGE_TAG__"
  digest: "__IMAGE_DIGEST__"

patches:
- target:
    kind: Ingress
    name: skylens
  patch: |-
    - op: replace
      path: /spec/rules/0/host
      value: __HOST__
