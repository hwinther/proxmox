# Cluster Architecture Plan

Single k0s cluster spanning Proxmox VMs and Raspberry Pi edge nodes, with Proxmox-level Ceph for persistent storage and Flux for GitOps.

## Target Architecture

```
┌─────────────────────────────────────────────────────┐
│                 One k0s Cluster                      │
│                                                      │
│  Control Plane: 1-3 Proxmox VMs (HA if 3)           │
│                                                      │
│  ┌─────────────────────────────────┐                 │
│  │ VM Workers (Proxmox, x86_64)   │  2-4 nodes      │
│  │ - General app workloads        │                  │
│  │ - Observability stack          │                  │
│  │ - Ingress (Traefik)            │                  │
│  │ - ceph-csi client              │                  │
│  └─────────────────────────────────┘                 │
│                                                      │
│  ┌─────────────────────────────────┐                 │
│  │ RPi Workers (ARM64, tainted)   │  2 nodes         │
│  │ - SDR workloads only           │                  │
│  │ - USB device passthrough       │                  │
│  │ - Active/passive failover      │                  │
│  │ - ceph-csi client              │                  │
│  └─────────────────────────────────┘                 │
│                                                      │
└─────────────────────────────────────────────────────┘
         ▲
         │ RBD / CephFS over network
         ▼
┌─────────────────────────────────────────────────────┐
│         Proxmox Ceph Cluster (3-5 nodes)             │
│   Runs on the hypervisor layer, managed via PVE UI   │
│   Provides storage to VMs and k8s via ceph-csi       │
└─────────────────────────────────────────────────────┘
```

## Setup Steps

### Phase 1: Networking — Cilium CNI

Cilium replaces both the CNI (pod-to-pod networking) and kube-proxy (service routing) using eBPF.

- [ ] Install Cilium via Helm on the k0s cluster
- [ ] Disable kube-proxy (k0s supports this in the config)
- [ ] Verify pod-to-pod connectivity across nodes
- [ ] Optionally enable Hubble for network observability

**Why Cilium**: eBPF-based, faster than iptables, built-in network policies, scales well, good observability via Hubble.

### Phase 2: Proxmox Ceph + ceph-csi

Storage runs at the Proxmox hypervisor level. Kubernetes nodes are thin clients.

#### Proxmox side

- [ ] Enable Ceph on 3+ Proxmox nodes
- [ ] Create OSDs from available disks
- [ ] Create an RBD pool for Kubernetes (e.g. `k8s-rbd`)
- [ ] Create a CephX auth key scoped to the k8s pool
- [ ] Note down the Ceph FSID and monitor addresses

#### Kubernetes side

- [ ] Deploy `ceph-csi-rbd` via HelmRelease (Flux)
- [ ] Create a Secret with Ceph monitor addresses and CephX key
- [ ] Create a `StorageClass` for Ceph RBD:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-rbd
provisioner: rbd.csi.ceph.com
parameters:
  clusterID: <ceph-fsid>
  pool: k8s-rbd
  csi.storage.k8s.io/provisioner-secret-name: csi-rbd-secret
  csi.storage.k8s.io/provisioner-secret-namespace: ceph-system
reclaimPolicy: Retain
allowVolumeExpansion: true
```

- [ ] Test a PVC claim and verify it provisions correctly

### Phase 3: Node Labeling and Taints

Control where workloads land using labels, taints, and tolerations.

#### Label nodes by role and capability

```bash
# VM workers
kubectl label node vm-worker-1 role=compute
kubectl label node vm-worker-2 role=compute

# Edge nodes
kubectl label node rpi-edge-1 role=sdr-edge
kubectl label node rpi-edge-2 role=sdr-edge
```

#### Taint edge nodes to repel general workloads

```bash
kubectl taint nodes rpi-edge-1 node-type=edge-sdr:NoSchedule
kubectl taint nodes rpi-edge-2 node-type=edge-sdr:NoSchedule
```

General pods will never land on RPi nodes unless they explicitly tolerate the taint.

### Phase 4: USB Device Passthrough (SDR on RPi)

Use `smarter-device-manager` to expose USB SDR devices to pods.

- [ ] Deploy `smarter-device-manager` as a DaemonSet on RPi nodes only (use nodeSelector)
- [ ] Configure the device list (map specific `/dev/` paths)
- [ ] Reference devices as resource requests in pod specs:

```yaml
spec:
  containers:
    - name: sdr-receiver
      resources:
        limits:
          smarter-devices/sdr0: 1
        requests:
          smarter-devices/sdr0: 1
```

### Phase 5: SDR Deployment with Active/Passive Failover

A single-replica Deployment that prefers the primary RPi but fails over to the backup.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sdr-receiver
  namespace: sdr
spec:
  replicas: 1
  template:
    spec:
      # Tolerate edge node taint
      tolerations:
        - key: "node-type"
          operator: "Equal"
          value: "edge-sdr"
          effect: "NoSchedule"
      affinity:
        nodeAffinity:
          # Must be an SDR edge node
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: role
                    operator: In
                    values: ["sdr-edge"]
          # Prefer primary RPi
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              preference:
                matchExpressions:
                  - key: kubernetes.io/hostname
                    operator: In
                    values: ["rpi-edge-1"]
      containers:
        - name: sdr-receiver
          # ...
```

**Failover behavior**: If `rpi-edge-1` goes down, the pod reschedules to `rpi-edge-2`. The Ceph RBD volume detaches and reattaches on the new node (expect ~60-120s for the Ceph blocklist timeout). The backup RPi must have equivalent USB SDR hardware.

### Phase 6: RBAC

Minimal RBAC for a homelab — most of it is handled automatically.

| Who/What | Access | Notes |
|---|---|---|
| You (admin) | `cluster-admin` | Via kubeconfig from k0s, already set up |
| Flux | `cluster-admin` | Built into Flux installation |
| Helm charts | Scoped per chart | ceph-csi, Traefik, Prometheus etc. include their own RBAC |
| App pods | None (default) | `default` service account has no API permissions |
| App needing API access | Custom Role | Create ServiceAccount + Role + RoleBinding per app |

- [ ] Organize workloads into namespaces (natural RBAC boundary):
  - `flux-system` — Flux controllers
  - `ceph-system` — ceph-csi
  - `traefik` — ingress controller
  - `observability` — Prometheus, Loki, Grafana, Tempo
  - `apps` — general application workloads
  - `sdr` — SDR edge workloads
- [ ] Create scoped ServiceAccounts only for pods that need Kubernetes API access

### Phase 7: Observability

Single observability stack on the VM workers, scraping all nodes including RPis.

- [ ] Prometheus scrapes all nodes and pods natively (no federation needed)
- [ ] Loki collects logs from all pods (Promtail/Alloy DaemonSet on every node including RPis)
- [ ] Grafana dashboards for SDR workloads, Ceph health, cluster overview
- [ ] Hubble (Cilium) for network flow visibility

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Single vs multi-cluster | **Single cluster** | 2 RPis don't justify multi-cluster overhead. Observability, networking, and storage are trivial in a single cluster. |
| Ceph location | **Proxmox layer** | Independent of k8s lifecycle. Serves both VM disks and k8s PVCs. Managed via Proxmox UI. |
| CNI | **Cilium** | eBPF-based, replaces kube-proxy, built-in network policies, Hubble observability. |
| Edge node isolation | **Taints + tolerations** | Prevents general workloads from landing on resource-constrained RPis. |
| USB passthrough | **smarter-device-manager** | Lightweight device plugin, well-suited for RPi/edge USB devices. |
| Failover model | **Active/passive** | Single replica with node affinity preference. Pod reschedules on node failure. |
| GitOps | **Flux (existing)** | Already in use in this repo. One Flux instance manages everything. |

## Prerequisites

- k0s installed on all nodes (Proxmox VMs + RPis)
- All nodes on the same LAN with reliable connectivity
- Proxmox Ceph configured with available disks
- Multi-arch container images for workloads that run on both x86_64 and ARM64
- USB SDR hardware on both RPi nodes (matching device configuration)
