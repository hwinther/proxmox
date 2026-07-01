apiVersion: v1
kind: Namespace
metadata:
  name: pbs-browser-preview-pr-__PR__
  labels:
    app.kubernetes.io/part-of: pbs-browser
    pbs-browser.wsh.no/preview: "true"
    pbs-browser.wsh.no/pr: "__PR__"
    # Kyverno clones the cluster-wide PBS encryption keyfile into namespaces with this label.
    pbs.wsh.no/encryption-keyfile: "true"
