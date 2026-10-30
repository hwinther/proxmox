apiVersion: v1
kind: Namespace
metadata:
  name: test-preview-pr-__PR__
  labels:
    app.kubernetes.io/part-of: test
    test.wsh.no/preview: "true"
    test.wsh.no/pr: "__PR__"
    # trust-manager renders the wsh-internal-ca ConfigMap here (the API mounts it for RabbitMQ TLS).
    wsh.no/trust-bundle: "true"
