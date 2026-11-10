apiVersion: v1
kind: Namespace
metadata:
  name: wshno-preview-pr-__PR__
  annotations:
    # The only hostname this preview's HTTPRoute may claim (bases/traefik-gateway/httproute-hostnames-policy.yaml).
    gateway.wsh.no/hostnames: "__HOST__"
  labels:
    # May attach HTTPRoutes to the platform Gateway (bases/traefik-gateway/gateway.yaml).
    gateway.wsh.no/traefik: "true"
    app.kubernetes.io/part-of: wshno
    wshno.wsh.no/preview: "true"
    wshno.wsh.no/pr: "__PR__"
