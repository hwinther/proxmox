apiVersion: v1
kind: Namespace
metadata:
  name: pbs-browser-fake-__PR__
  annotations:
    # The only hostname this env's HTTPRoute may claim (bases/traefik-gateway/httproute-hostnames-policy.yaml).
    gateway.wsh.no/hostnames: "__HOST__"
  labels:
    # May attach HTTPRoutes to the platform Gateway (bases/traefik-gateway/gateway.yaml); Kyverno also puts the
    # authelia-forwardauth Middleware here for ExtensionRef filters.
    gateway.wsh.no/traefik: "true"
    app.kubernetes.io/part-of: pbs-browser
    pbs-browser.wsh.no/fake-env: "__PR__"
    # Deliberately NOT pbs-browser.wsh.no/preview or pbs.wsh.no/encryption-keyfile: those labels make
    # Kyverno clone the PBS credentials and the encryption keyfile, and this env must have neither.
