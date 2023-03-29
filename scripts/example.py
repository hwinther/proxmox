from src.lxc.actions import update_lxc_templates
from src.lxc.distro.alpine.actions import AlpineContainer
from src.lxc.distro.alpine.services.bind import install_bind_dns
from src.lxc.distro.alpine.services.dhcpd import install_isc_dhcpd
from src.lxc.distro.alpine.services.gateway import install_gateway_nat
from src.lxc.models import NetworkInterface, Subnet


def main():
    alpine_newest_image_name = update_lxc_templates()
    # TODO: translate image names not just for local (template_)storage?
    image_path = f'/var/lib/vz/template/cache/{alpine_newest_image_name}'

    # Create NAT gateway
    nat_gateway = AlpineContainer(601)
    nat_gateway.purge_container()
    nat_gateway.create_container('gateway-test', image_path, [NetworkInterface(),
                                                              NetworkInterface(vlan_tag=100, ip4='10.100.0.1/24')],
                                 startup=1)
    nat_gateway.update_container()
    # TODO: rewrite to interface instance? from NetworkInterfaces that were specified in create_container
    print(nat_gateway.get_ip(0))
    print(nat_gateway.get_ip(1))
    install_gateway_nat(nat_gateway)

    # Create DNS server
    dns_server = AlpineContainer(602)
    dns_server.purge_container()
    dns_server.create_container('dns-test', image_path, [NetworkInterface(vlan_tag=100,
                                                                          ip4='10.100.0.2/24',
                                                                          gw4='10.100.0.1')], startup=1)
    dns_server.update_container()
    print(dns_server.get_ip(0))
    install_bind_dns(dns_server, '10.100.0')

    # Create DHCP server
    dhcp_server = AlpineContainer(603)
    dhcp_server.purge_container()
    # TODO: create_container should return a container instance
    dhcp_server.create_container('dhcp-test', image_path, [NetworkInterface(vlan_tag=100,
                                                                            ip4='10.100.0.3/24',
                                                                            gw4='10.100.0.1')], startup=1)
    dhcp_server.update_container()
    print(dhcp_server.get_ip(0))
    install_isc_dhcpd(dhcp_server,
                      [Subnet(network='10.100.0.0/24',
                              range_start=100,
                              range_end=200,
                              router='10.100.0.1',
                              domain_name='test.lan',
                              # domain_name_servers=['10.100.0.2'])], # TODO: reference dns container's IP here
                              domain_name_servers=['10.100.0.2'])],
                      [])

    # Create test client that uses the previously created DHCP server to acquire an IP
    client = AlpineContainer(604)
    client.purge_container()
    client.create_container('client-test', image_path, [NetworkInterface(vlan_tag=100)], startup=1)
    client.update_container()
    # time.sleep(1)
    print(client.get_ip(0))
    print(client.pct_console_shell('uname -a'))


if __name__ == '__main__':
    main()
