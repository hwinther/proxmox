apiVersion: v1
kind: Namespace
metadata:
  name: ddnsadmin-preview-pr-__PR__
  annotations:
    # The only hostname this preview's HTTPRoute may claim (../../../traefik/httproute-hostnames-policy.yaml).
    gateway.wsh.no/hostnames: "__HOST__"
  labels:
    # May attach HTTPRoutes to the platform Gateway (../../../traefik/gateway.yaml); Kyverno also puts the
    # authelia-forwardauth Middleware here for ExtensionRef filters.
    gateway.wsh.no/traefik: "true"
    app.kubernetes.io/part-of: ddnsadmin
    ddnsadmin.wsh.no/preview: "true"
    ddnsadmin.wsh.no/pr: "__PR__"
