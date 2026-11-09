# Gateway API CRDs (production)

`standard-install.yaml` is the upstream **standard channel** bundle, **v1.6.3**, unmodified:
`https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.3/standard-install.yaml`.
It contains the CRDs (GatewayClass, Gateway, HTTPRoute, GRPCRoute, ReferenceGrant, ...) and the
upstream `safe-upgrades` ValidatingAdmissionPolicy. That policy stops experimental-channel CRDs from
being installed over these ones.

Version: Traefik v3.7 supports Gateway API standard v1.6.3 (Traefik kubernetesGateway provider docs).
Pick the version Traefik documents for the running release. Don't pick the newest upstream release.
Leave the Traefik provider's `experimentalChannel` off: turning it on without the experimental CRDs
stops the Gateway provider from serving anything. HTTPRoute is standard.

Cilium also implements Gateway API, but `gatewayAPI.enabled` is not set in
`../cilium/helmrelease.yaml`. Keep it that way so only Traefik reconciles Gateways.

Bump (together with a Traefik bump that documents the new version):

```bash
curl -sSLo clusters/production/apps/gateway-api/standard-install.yaml \
  https://github.com/kubernetes-sigs/gateway-api/releases/download/<version>/standard-install.yaml
```

The platform Gateway is `traefik/traefik` in `../traefik/gateway.yaml`.
