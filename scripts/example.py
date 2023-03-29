from src.lxc.actions import create_container, pct_console_shell, purge_container, update_lxc_templates
from src.lxc.distro.alpine.actions import get_ip, update_container
from src.lxc.distro.alpine.services.bind import install_bind_dns
from src.lxc.distro.alpine.services.dhcpd import install_isc_dhcpd
from src.lxc.distro.alpine.services.gateway import install_gateway_nat
from src.lxc.models import NetworkInterface, Subnet


def main():
    alpine_newest_image_name = update_lxc_templates()
    # TODO: translate image names not just for local (template_)storage?
    image_path = f'/var/lib/vz/template/cache/{alpine_newest_image_name}'

    # Create NAT gateway
    cid = 601
    purge_container(cid)
    create_container(cid, 'gateway-test', image_path, [NetworkInterface(),
                                                       NetworkInterface(vlan_tag=100, ip4='10.100.0.1/24')],
                     startup=1)
    update_container(cid)
    print(get_ip(cid, 0))
    print(get_ip(cid, 1))
    install_gateway_nat(cid)

    # Create DNS server
    cid = 602
    purge_container(cid)
    create_container(cid, 'dns-test', image_path, [NetworkInterface(vlan_tag=100,
                                                                    ip4='10.100.0.2/24',
                                                                    gw4='10.100.0.1')], startup=1)
    update_container(cid)
    print(get_ip(cid, 0))
    install_bind_dns(cid, '10.100.0')

    # Create DHCP server
    cid = 603
    purge_container(cid)
    # TODO: create_container should return a container instance
    create_container(cid, 'dhcp-test', image_path, [NetworkInterface(vlan_tag=100,
                                                                     ip4='10.100.0.3/24',
                                                                     gw4='10.100.0.1')], startup=1)
    update_container(cid)
    print(get_ip(cid, 0))
    install_isc_dhcpd(cid,
                      [Subnet(network='10.100.0.0/24',
                              range_start=100,
                              range_end=200,
                              router='10.100.0.1',
                              domain_name='test.lan',
                              # domain_name_servers=['10.100.0.2'])], # TODO: reference dns container's IP here
                              domain_name_servers=['10.100.0.2'])],
                      [])

    # Create test client that uses the previously created DHCP server to acquire an IP
    cid = 604
    purge_container(cid)
    create_container(cid, 'client-test', image_path, [NetworkInterface(vlan_tag=100)], startup=1)
    update_container(cid)
    # time.sleep(1)
    print(get_ip(cid, 0))
    print(pct_console_shell(cid, 'uname -a'))


if __name__ == '__main__':
    main()
