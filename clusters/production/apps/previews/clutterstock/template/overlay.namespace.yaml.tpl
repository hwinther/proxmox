apiVersion: v1
kind: Namespace
metadata:
  name: clutterstock-preview-pr-__PR__
  annotations:
    # The only hostname this preview's HTTPRoute may claim (../../../traefik/httproute-hostnames-policy.yaml).
    gateway.wsh.no/hostnames: "__HOST__"
  labels:
    # May attach HTTPRoutes to the platform Gateway (../../../traefik/gateway.yaml); Kyverno also puts the
    # authelia-forwardauth Middleware here for ExtensionRef filters.
    gateway.wsh.no/traefik: "true"
    app.kubernetes.io/part-of: clutterstock
    clutterstock.wsh.no/preview: "true"
    clutterstock.wsh.no/pr: "__PR__"
