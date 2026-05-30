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

# Single image: digest pins the deploy to exactly the artifact that just passed e2e + grype; the
# tag (newTag) is kept alongside so `kubectl get deploy -o yaml | grep image:` stays readable.
images:
- name: ghcr.io/hwinther/ddnsadmin/ddnsadmin
  newTag: "__IMAGE_TAG__"
  digest: "__IMAGE_DIGEST__"

patches:
# WEB_PREFIX drives the absolute URLs Django emits (django-environ reads it in dweb/settings.py),
# so it must point at the per-PR preview host. The ingress host is rewritten to match.
- target:
    kind: Deployment
    name: ddnsadmin
  patch: |-
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: ddnsadmin
    spec:
      template:
        spec:
          containers:
          - name: ddnsadmin
            env:
            - name: WEB_PREFIX
              value: "https://__HOST__"
- target:
    kind: Ingress
    name: ddnsadmin
  patch: |-
    - op: replace
      path: /spec/rules/0/host
      value: __HOST__
