from typing import Sequence, Union
from ipaddress import IPv4Address, IPv6Address, IPv4Network, ip_network, ip_address


class NetworkInterface:
    vlan_tag: int = None
    firewall: bool = None
    bridge: str = None
    ip4: str = None
    gw4: str = None
    ip6: str = None
    gw6: str = None

    def __init__(self, vlan_tag: int = None, firewall: bool = True, bridge: str = None,
                 ip4: str = None, gw4: str = None, ip6: str = None, gw6: str = None):
        # TODO: replace ip4/ip6 with ipaddress.ip_address
        self.vlan_tag = vlan_tag
        self.firewall = firewall
        self.bridge = bridge
        self.ip4 = ip4
        self.gw4 = gw4
        self.ip6 = ip6
        self.gw6 = gw6


class Subnet:
    network: IPv4Network = None
    range_start: IPv4Address = None
    range_end: IPv4Address = None
    router: IPv4Address = None
    domain_name = None
    domain_name_servers: Sequence[Union[IPv4Address, IPv6Address]] = None
    netbios_name_servers: Sequence[Union[IPv4Address, IPv6Address]] = None
    ntp_servers: Sequence[Union[IPv4Address, IPv6Address]] = None

    def __init__(self, network: str, range_start: int, range_end: int,
                 router: str, domain_name: str,
                 domain_name_servers: Sequence[str],
                 netbios_name_servers: Sequence[str] = None,
                 ntp_servers: Sequence[str] = None):
        # TODO: IPv6 support
        self.network = ip_network(network)
        self.range_start = self.network.network_address + range_start
        self.range_end = self.network.network_address + range_end
        self.router = ip_address(router)

        self.domain_name = domain_name

        self.domain_name_servers = [ip_address(ip) for ip in domain_name_servers]
        if netbios_name_servers is None:
            netbios_name_servers = []
        self.netbios_name_servers = [ip_address(ip) for ip in netbios_name_servers]
        if ntp_servers is None:
            ntp_servers = []
        self.ntp_servers = [ip_address(ip) for ip in ntp_servers]


class Device:
    hostname: str = None
    hardware_ethernet: str = None
    fixed_address: IPv4Address = None

    def __init__(self, hostname: str, hardware_ethernet: str, fixed_address: str):
        self.hostname = hostname
        self.hardware_ethernet = hardware_ethernet
        self.fixed_address = ip_address(fixed_address)
