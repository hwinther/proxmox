apiVersion: v1
kind: Namespace
metadata:
  name: pbs-browser-preview-pr-__PR__
  annotations:
    # The only hostname this preview's HTTPRoute may claim (bases/traefik-gateway/httproute-hostnames-policy.yaml).
    gateway.wsh.no/hostnames: "__HOST__"
  labels:
    # May attach HTTPRoutes to the platform Gateway (bases/traefik-gateway/gateway.yaml); Kyverno also puts the
    # authelia-forwardauth Middleware here for ExtensionRef filters.
    gateway.wsh.no/traefik: "true"
    app.kubernetes.io/part-of: pbs-browser
    pbs-browser.wsh.no/preview: "true"
    pbs-browser.wsh.no/pr: "__PR__"
    # Kyverno clones the cluster-wide PBS encryption keyfile into namespaces with this label.
    pbs.wsh.no/encryption-keyfile: "true"
