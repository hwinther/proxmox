#!/usr/bin/env bash
# Reconvergence GO/WAIT gate for the k0s production cluster. Run this BEFORE
# rebooting (or upgrading) the next control-plane node during any rolling
# maintenance — only proceed on GO, and never take a second control-plane node
# down on WAIT (that drops etcd quorum: 3 members, needs 2).
#
# Checks (all must PASS for GO):
#   1. every Kubernetes node is Ready
#   2. etcd /health == true on every reachable control-plane member
#   3. cilium-operator pods Running AND not accumulating restarts over a window
#   4. all cilium agent pods Running/Ready
#
# Read-only. Run from a host with `kubectl` (Production context) and SSH access
# to the controllers. Exit 0 = GO (safe), 1 = WAIT (do not reboot another node).
#
# Env overrides:
#   KUBE_CONTEXT  kubectl context            (default: Production)
#   CP_NODES      control-plane node IPs/host (default: prod01 prod02 prod04)
#   SSH_USER      ssh user for the nodes      (default: root)
# Arg: $1 = restart-stability window seconds  (default: 30)
#
# Usage:  scripts/k0s-reconverge-check.sh [stability_window_seconds]

set -u

CTX="${KUBE_CONTEXT:-Production}"
CP_NODES="${CP_NODES:-10.20.13.11 10.20.13.12 10.20.13.14}"   # prod01 prod02 prod04 (etcd members)
SSH_USER="${SSH_USER:-root}"
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 -o BatchMode=yes"
WINDOW="${1:-30}"

green() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
red()   { printf '  \033[31mFAIL\033[0m %s\n' "$1"; }
info()  { printf '\n== %s ==\n' "$1"; }

FAIL=0

# ---- 1. nodes Ready --------------------------------------------------------
info "1. Kubernetes nodes"
NODES=$(kubectl --context="$CTX" get nodes --no-headers 2>/dev/null)
if [ -z "$NODES" ]; then
  red "could not query nodes (apiserver unreachable?)"; FAIL=1
else
  while read -r name status _; do
    [ -z "$name" ] && continue
    if [ "$status" = "Ready" ]; then green "$name Ready"
    else red "$name = $status"; FAIL=1; fi
  done <<EOF
$NODES
EOF
fi

# ---- 2. etcd health on each control-plane member ---------------------------
info "2. etcd /health (per control-plane node)"
for ip in $CP_NODES; do
  H=$(ssh $SSH_OPTS "$SSH_USER@$ip" '
    wget --no-check-certificate -q -O- --timeout=5 \
      --ca-certificate=/var/lib/k0s/pki/etcd/ca.crt \
      --certificate=/var/lib/k0s/pki/apiserver-etcd-client.crt \
      --private-key=/var/lib/k0s/pki/apiserver-etcd-client.key \
      https://127.0.0.1:2379/health 2>/dev/null \
    || curl -s --max-time 5 \
      --cacert /var/lib/k0s/pki/etcd/ca.crt \
      --cert /var/lib/k0s/pki/apiserver-etcd-client.crt \
      --key /var/lib/k0s/pki/apiserver-etcd-client.key \
      https://127.0.0.1:2379/health 2>/dev/null' 2>/dev/null)
  case "$H" in
    *'"health":"true"'*) green "$ip etcd healthy" ;;
    "") red "$ip unreachable / etcd not answering (rebooting?)"; FAIL=1 ;;
    *)  red "$ip etcd unhealthy: $H"; FAIL=1 ;;
  esac
done

# ---- 3. cilium-operator: Running + restart-stable over WINDOW --------------
info "3. cilium-operator stability (${WINDOW}s window)"
op_state() {
  kubectl --context="$CTX" -n kube-system get pods -l io.cilium/app=operator \
    --no-headers 2>/dev/null
}
OP1=$(op_state)
[ -z "$OP1" ] && OP1=$(kubectl --context="$CTX" -n kube-system get pods --no-headers 2>/dev/null | grep '^cilium-operator')
if [ -z "$OP1" ]; then
  red "no cilium-operator pods found"; FAIL=1
else
  R1=$(echo "$OP1" | awk '{s+=$4} END{print s+0}')
  NOTRUN=$(echo "$OP1" | awk '$3!="Running"{print $1" "$3}')
  [ -n "$NOTRUN" ] && { red "operator not Running: $NOTRUN"; FAIL=1; }
  sleep "$WINDOW"
  OP2=$(op_state); [ -z "$OP2" ] && OP2=$(kubectl --context="$CTX" -n kube-system get pods --no-headers 2>/dev/null | grep '^cilium-operator')
  R2=$(echo "$OP2" | awk '{s+=$4} END{print s+0}')
  if [ "$R1" = "$R2" ]; then green "operator restarts stable ($R2, no change in ${WINDOW}s)"
  else red "operator still crash-looping (restarts $R1 -> $R2 in ${WINDOW}s)"; FAIL=1; fi
fi

# ---- 4. cilium agents Running/Ready ---------------------------------------
info "4. cilium agent pods"
AG=$(kubectl --context="$CTX" -n kube-system get pods --no-headers 2>/dev/null \
      | grep '^cilium-' | grep -vE 'cilium-operator|cilium-envoy')
if [ -z "$AG" ]; then
  red "no cilium agent pods found"; FAIL=1
else
  BAD=$(echo "$AG" | awk '{split($2,a,"/"); if($3!="Running"||a[1]!=a[2]) print "  "$1" "$2" "$3}')
  if [ -z "$BAD" ]; then green "all $(echo "$AG" | wc -l | tr -d ' ') cilium agents Running/Ready"
  else red "unhealthy cilium agents:"; echo "$BAD"; FAIL=1; fi
fi

# ---- verdict ---------------------------------------------------------------
echo
if [ "$FAIL" -eq 0 ]; then
  printf '\033[32m==== GO ====\033[0m  reconverged — safe to reboot the next control-plane node (one at a time)\n'
  exit 0
else
  printf '\033[31m==== WAIT ====\033[0m  not converged — do NOT reboot another node yet; re-run shortly\n'
  exit 1
fi
