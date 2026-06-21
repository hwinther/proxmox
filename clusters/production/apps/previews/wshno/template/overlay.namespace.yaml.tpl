apiVersion: v1
kind: Namespace
metadata:
  name: wshno-preview-pr-__PR__
  labels:
    app.kubernetes.io/part-of: wshno
    wshno.wsh.no/preview: "true"
    wshno.wsh.no/pr: "__PR__"
