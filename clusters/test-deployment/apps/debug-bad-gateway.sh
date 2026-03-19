#!/usr/bin/env bash
# Debug Bad Gateway: run from machine with kubectl + cluster access
# Usage: ./debug-bad-gateway.sh [namespace]
# On k0s: uses k0s kubectl when plain kubectl is missing
set -e
NS="${1:-test}"
if command -v kubectl >/dev/null 2>&1; then
  KUBECTL=(kubectl)
elif command -v k0s >/dev/null 2>&1; then
  KUBECTL=(k0s kubectl)
else
  echo "Need kubectl or k0s on PATH"
  exit 1
fi

echo "=== 1. Pods in $NS ==="
"${KUBECTL[@]}" get pods -n "$NS" -o wide
echo ""

echo "=== 2. Services & Endpoints (no endpoints = Bad Gateway) ==="
"${KUBECTL[@]}" get svc,endpoints -n "$NS"
echo ""

echo "=== 3. Ingress in $NS ==="
"${KUBECTL[@]}" get ingress -n "$NS"
echo ""

echo "=== 4. Pod not Ready? (describe) ==="
for p in $("${KUBECTL[@]}" get pods -n "$NS" -o name); do
  echo "--- $p ---"
  "${KUBECTL[@]}" get "$p" -n "$NS" -o jsonpath='{.status.phase} | Ready: {.status.conditions[?(@.type=="Ready")].status}{"\n"}'
  "${KUBECTL[@]}" get "$p" -n "$NS" -o jsonpath='  Container ports: {range .spec.containers[*]}{.name}={.ports[*].containerPort}{"\n"}{end}'
  echo ""
done

echo "=== 5. Recent pod events (look for CrashLoopBackOff, ImagePullBackOff) ==="
"${KUBECTL[@]}" get events -n "$NS" --sort-by='.lastTimestamp' | tail -20
echo ""

echo "=== 6. Quick in-cluster HTTP check (clutterstock-frontend:8080) ==="
if "${KUBECTL[@]}" run curl-debug --rm -i --restart=Never -n "$NS" --image=curlimages/curl --overrides='{"spec":{"terminationGracePeriodSeconds":0}}' -- curl -s -o /dev/null -w "HTTP %{http_code}\n" --connect-timeout 3 http://clutterstock-frontend:8080/ 2>/dev/null; then
  true
else
  echo "Request failed (timeout or connection refused)"
fi
echo ""

echo "=== 7. Quick in-cluster HTTP check (clutterstock-api:8080) ==="
if "${KUBECTL[@]}" run curl-debug-api --rm -i --restart=Never -n "$NS" --image=curlimages/curl --overrides='{"spec":{"terminationGracePeriodSeconds":0}}' -- curl -s -o /dev/null -w "HTTP %{http_code}\n" --connect-timeout 3 http://clutterstock-api:8080/ 2>/dev/null; then
  true
else
  echo "Request failed (timeout or connection refused)"
fi

echo ""
echo "Next: compare pod logs 'listening on' port vs Deployment containerPort / Service targetPort."
echo "      e.g. ${KUBECTL[*]} logs -n $NS deploy/clutterstock-frontend"
echo "If container listens on another port (e.g. 5173 or 5000), fix containerPort in Deployment and Service."
