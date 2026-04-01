# Homelab Network Plan (OPNsense + Proxmox + k0s + Ceph)

This is a practical starting design for your topology:

- separate admin/mgmt network
- k0s cluster node network
- Ceph public network
- Ceph replication network

Adjust CIDRs/VLAN IDs to your environment, but keep the separation model.

## Suggested VLAN and CIDR layout


| Purpose                   | VLAN (example) | CIDR (example)  | Internet egress  |
| ------------------------- | -------------- | --------------- | ---------------- |
| Admin / infra management  | `10`           | `10.10.10.0/24` | Yes (restricted) |
| k0s node network          | `20`           | `10.10.20.0/24` | Yes (restricted) |
| Ceph public (client path) | `30`           | `10.10.30.0/24` | No               |
| Ceph replication          | `31`           | `10.10.31.0/24` | No               |


### Naming

- Use `ceph-public` for Ceph client-facing network.
- Use `ceph-replication` for OSD east-west traffic.

## What each network is used for

- **Admin**: Proxmox UI/SSH, switch/AP management, OPNsense management, jump hosts.
- **k0s node**: controller/worker IPs, Kubernetes API access, ingress/controller traffic, GitOps and image pulls.
- **ceph-public**: k0s nodes and Ceph clients to Ceph mons/osds.
- **ceph-replication**: Ceph internal replication/backfill/recovery only.

## CIDR planning rules

- Do not overlap:
  - any VLAN subnet above
  - k0s `podCIDR`
  - k0s `serviceCIDR`
- Example k0s ranges that avoid conflicts with the example VLANs:
  - `podCIDR: 10.244.0.0/16`
  - `serviceCIDR: 10.96.0.0/12`

## OPNsense policy model

Prefer **per-interface rules** (clear intent), with aliases to reduce repetition.

### Useful aliases

- `K0S_NODES` = controller/worker IPs
- `CEPH_NODES` = all Ceph node IPs (on ceph-public/replication)
- `CEPH_PUBLIC_NET` = ceph-public subnet
- `CEPH_REPL_NET` = ceph-replication subnet
- `FW_DNS_NTP` = OPNsense interface address(es), ports `53` + `123`

## Inter-VLAN allow matrix (starting baseline)


| Source           | Destination                        | Ports/Proto                                                 | Why                               |
| ---------------- | ---------------------------------- | ----------------------------------------------------------- | --------------------------------- |
| Admin            | k0s node                           | `6443/tcp`, `22/tcp` (optional), `10250/tcp` (optional ops) | kubectl/API + maintenance         |
| Admin            | Ceph public                        | Ceph admin/client ports as needed                           | Ceph admin access                 |
| k0s node         | Internet                           | `443/tcp`, `80/tcp` (minimize), `53`, `123`                 | image pulls, charts, git, updates |
| k0s node         | ceph-public                        | Ceph client path (mon + OSD/client)                         | CSI and storage IO                |
| k0s node         | ceph-replication                   | Deny                                                        | not needed for clients            |
| ceph-public      | OPNsense                           | `53`, `123` only                                            | DNS/NTP only                      |
| ceph-public      | Internet                           | Deny                                                        | harden storage path               |
| ceph-replication | OPNsense                           | `53`, `123` only                                            | DNS/NTP only                      |
| ceph-replication | Internet                           | Deny                                                        | harden replication path           |
| ceph-replication | ceph-replication (Ceph nodes only) | Ceph replication/internal ports                             | OSD replication/backfill          |


## k0s-specific required paths

From k0s workers to controllers:

- `6443/tcp` kube-apiserver
- `8132/tcp` konnectivity

If these are blocked, nodes will fail to function correctly.

## Ceph-specific intent

- Kubernetes `StorageClass` (Ceph CSI) should use **ceph-public** endpoints.
- Keep **ceph-replication** isolated to Ceph nodes only.

## OPNsense rule order (per Ceph interface)

For both `ceph-public` and `ceph-replication` interfaces:

1. Allow DHCP (if used)
2. Allow DNS/NTP to OPNsense
3. Allow required Ceph peer traffic (node aliases only)
4. Block to WAN / Internet
5. Block any remaining inter-VLAN traffic unless explicitly needed

Do not rely on broad floating allow rules. Use floating rules only for cross-cutting behavior (logging, shaping) when necessary.

## DNS/Ingress naming alignment (already chosen)

- prod: `appname.wsh.no`
- test: `appname.test.wsh.no`
- preview: `appname-<pr-number>.preview.wsh.no`

This is independent of VLANs; VLANs control packet paths, while hostnames map at DNS + Ingress.

## Validation checklist

- All VLAN subnets are non-overlapping
- `podCIDR`/`serviceCIDR` do not overlap any VLAN
- k0s worker -> controller `6443` and `8132` allowed
- k0s node -> ceph-public allowed; k0s node -> ceph-replication denied
- ceph-public and ceph-replication have no WAN egress
- DNS/NTP to OPNsense works from all internal VLANs
- Ceph health remains OK during rebalance/recovery

