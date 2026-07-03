apiVersion: v1
kind: Namespace
metadata:
  name: skylens-preview-pr-__PR__
  labels:
    app.kubernetes.io/part-of: skylens
    skylens.wsh.no/preview: "true"
    skylens.wsh.no/pr: "__PR__"
