from __future__ import annotations

from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    ip_address,
)
from typing import Sequence, Union


class NetworkInterface:
    vlan_tag: int | None = None
    firewall: bool = True
    bridge: str | None = None
    mac: str | None = None
    ip4: IPv4Interface | None = None
    gw4: IPv4Address | None = None
    ip6: IPv6Interface | None = None
    gw6: IPv6Address | None = None

    def __init__(
        self,
        vlan_tag: int = None,
        firewall: bool = True,
        bridge: str = None,
        mac: str = None,
        ip4: str = None,
        gw4: str = None,
        ip6: str = None,
        gw6: str = None,
    ):
        self.vlan_tag = vlan_tag
        self.firewall = firewall
        self.bridge = bridge
        self.mac = mac
        if ip4 is not None:
            self.ip4 = IPv4Interface(ip4)
        if gw4 is not None:
            self.gw4 = IPv4Address(gw4)
        if ip6 is not None:
            self.ip6 = IPv6Interface(ip6)
        if gw6 is not None:
            self.gw6 = IPv6Address(gw6)


class Subnet:
    network: IPv4Network
    range_start: IPv4Address
    range_end: IPv4Address
    router: IPv4Address
    domain_name: str
    domain_name_servers: Sequence[Union[IPv4Address, IPv6Address]]
    netbios_name_servers: Sequence[Union[IPv4Address, IPv6Address]]
    ntp_servers: Sequence[Union[IPv4Address, IPv6Address]]

    def __init__(
        self,
        network: str,
        range_start: int,
        range_end: int,
        router: str,
        domain_name: str,
        domain_name_servers: Sequence[str],
        netbios_name_servers: Sequence[str] = None,
        ntp_servers: Sequence[str] = None,
    ):
        # TODO: IPv6 support
        self.network = IPv4Network(network)
        self.range_start = self.network.network_address + range_start
        self.range_end = self.network.network_address + range_end
        self.router = IPv4Address(router)

        self.domain_name = domain_name

        self.domain_name_servers = [ip_address(ip) for ip in domain_name_servers]
        if netbios_name_servers is None:
            netbios_name_servers = []
        self.netbios_name_servers = [ip_address(ip) for ip in netbios_name_servers]
        if ntp_servers is None:
            ntp_servers = []
        self.ntp_servers = [ip_address(ip) for ip in ntp_servers]


class Device:
    hostname: str
    hardware_ethernet: str
    fixed_address: IPv4Address

    def __init__(self, hostname: str, hardware_ethernet: str, fixed_address: str):
        self.hostname = hostname
        self.hardware_ethernet = hardware_ethernet
        self.fixed_address = IPv4Address(fixed_address)
