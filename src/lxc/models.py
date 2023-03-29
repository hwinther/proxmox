from ipaddress import IPv4Address, IPv4Interface, IPv4Network, IPv6Address, IPv6Interface, ip_address, ip_interface, \
    ip_network
from typing import Sequence, Union


class NetworkInterface:
    vlan_tag: int = None
    firewall: bool = None
    bridge: str = None
    ip4: IPv4Interface = None
    gw4: IPv4Address = None
    ip6: IPv6Interface = None
    gw6: IPv6Address = None

    def __init__(self, vlan_tag: int = None, firewall: bool = True, bridge: str = None,
                 ip4: str = None, gw4: str = None, ip6: str = None, gw6: str = None):
        self.vlan_tag = vlan_tag
        self.firewall = firewall
        self.bridge = bridge
        if ip4 is not None:
            self.ip4 = ip_interface(ip4)
        if gw4 is not None:
            self.gw4 = ip_address(gw4)
        if ip6 is not None:
            self.ip6 = ip_interface(ip6)
        if gw6 is not None:
            self.gw6 = ip_address(gw6)


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
