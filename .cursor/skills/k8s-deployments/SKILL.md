---
name: k8s-deployments
description: >-
  Create and modify Kubernetes Deployment and Service manifests following this
  repo's conventions. Use when adding a new workload, updating container images,
  changing resource limits, or configuring environment variables for deployments.
---

# Kubernetes Deployments and Services

## File Conventions

- **Filename:** `<app-name>-deployment.yaml`
- **Location:** `clusters/test-deployment/apps/`
- **Structure:** Deployment and Service in the same file, separated by `---`
- **Registration:** Add the filename to `clusters/test-deployment/apps/kustomization.yaml` under `resources`

## Namespace

All app workloads use namespace `test`.

## Template

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <app-name>
  namespace: test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: <app-name>
  template:
    metadata:
      labels:
        app: <app-name>
    spec:
      containers:
      - name: <app-name>
        image: ghcr.io/hwinther/<project>/<component>:<semver>
        imagePullPolicy: Always
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        env:
        - name: OTEL_SERVICE_NAME
          value: "<app-name>"
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://obs-otel-collector.test.svc.cluster.local:4317"
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
---
apiVersion: v1
kind: Service
metadata:
  name: <app-name>
  namespace: test
spec:
  type: ClusterIP
  ports:
  - port: 8080
    targetPort: http
    protocol: TCP
    name: http
  selector:
    app: <app-name>
```

## Patterns

### Labels

Use a single `app: <name>` label on `selector.matchLabels` and `template.metadata.labels`. The Deployment name, container name, Service name, and label value should all match.

### Images

- Registry: `ghcr.io/hwinther/<project>/<component>:<semver>`
- Always use a **semver tag** (e.g. `1.0.0`, `0.53.1`), never `latest`.
- Set `imagePullPolicy: Always` so re-pushed tags (e.g. during development) are pulled.

### Resource Requests and Limits

Every container must have `resources.requests` and `resources.limits`. Typical starting values:

| | CPU | Memory |
|---|---|---|
| Request | `100m` | `256Mi` |
| Limit | `500m` | `512Mi` |

Adjust based on actual workload profiling.

### OTEL Instrumentation

All app containers include OpenTelemetry environment variables:

- `OTEL_SERVICE_NAME` -- matches the app name for trace/metric identity.
- `OTEL_EXPORTER_OTLP_ENDPOINT` -- points to the in-cluster OTEL Collector gRPC endpoint: `http://obs-otel-collector.test.svc.cluster.local:4317`.

For apps that also need trace-specific config (e.g. .NET), add:

```yaml
- name: OTEL_TRACES_EXPORTER
  value: "otlp"
- name: OTEL_EXPORTER_OTLP_PROTOCOL
  value: "grpc"
```

### Ports

- Container port name: `http`
- Default port: `8080`
- Service type: `ClusterIP` (Traefik Ingress handles external access)
- Service `targetPort` references the named port `http`, not the number

## Checklist for New Deployments

1. Create `<app>-deployment.yaml` from the template above.
2. Replace all `<app-name>`, `<project>`, `<component>`, `<semver>` placeholders.
3. Add the filename to `clusters/test-deployment/apps/kustomization.yaml`.
4. Add an Ingress entry in `clusters/test-deployment/apps/ingress.yaml` if external access is needed.
5. Commit to `main` for Flux to reconcile.
