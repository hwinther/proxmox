from src.lxc.actions import update_lxc_templates
from src.lxc.distro.alpine.actions import AlpineContainer
from src.lxc.distro.alpine.services.bind import BindService, MasterZone, SlaveZone
from src.lxc.distro.alpine.services.dhcpd import DhcpService
from src.lxc.distro.alpine.services.gateway import GatewayService
from src.lxc.models import NetworkInterface, Subnet


def main():
    alpine_newest_image_name = update_lxc_templates()
    # TODO: translate image names not just for local (template_)storage?
    image_path = f'/var/lib/vz/template/cache/{alpine_newest_image_name}'

    # for i in range(601, 607):
    #     print(i)
    #     Container.purge_container_by_id(i)
    #
    # return

    # Create NAT gateway
    nat_gateway = AlpineContainer(601)
    nat_gateway.purge_container()
    nat_gateway.create_container('gateway-test',
                                 image_path,
                                 [NetworkInterface(),
                                  NetworkInterface(vlan_tag=100,
                                                   ip4='10.100.0.1/24')],
                                 onboot=1)
    nat_gateway.update_container()
    # TODO: rewrite to interface instance? from NetworkInterfaces that were specified in create_container
    print(nat_gateway.get_ip(0))
    print(nat_gateway.get_ip(1))
    gateway_service = GatewayService(nat_gateway, 'gateway for internal lan')
    gateway_service.install()

    # Create DNS server
    dns_server = AlpineContainer(602)
    dns_server.purge_container()
    dns_server.create_container('dns-test',
                                image_path,
                                [NetworkInterface(vlan_tag=100,
                                                  ip4='10.100.0.2/24',
                                                  gw4='10.100.0.1')],
                                onboot=1)
    dns_server.update_container()
    print(dns_server.get_ip(0))
    dns_service = BindService(dns_server, 'dns recursive resolver')
    dns_service.install_bind_dns_recursive(dns_server.network_interfaces[0])

    # Create DHCP server
    dhcp_server = AlpineContainer(603)
    dhcp_server.purge_container()
    dhcp_server.create_container('dhcp-test',
                                 image_path,
                                 [NetworkInterface(vlan_tag=100,
                                                   ip4='10.100.0.3/24',
                                                   gw4='10.100.0.1')],
                                 onboot=1)
    dhcp_server.update_container()
    print(dhcp_server.get_ip(0))
    dhcp_service = DhcpService(dhcp_server, 'isc dhcpd service')
    dhcp_service.install([Subnet(network='10.100.0.0/24',
                                 range_start=100,
                                 range_end=200,
                                 router=str(nat_gateway.network_interfaces[1].ip4.ip),
                                 domain_name='test.lan',
                                 domain_name_servers=[str(dns_server.network_interfaces[0].ip4.ip)])],
                         [])

    # Create test client that uses the previously created DHCP server to acquire an IP
    client = AlpineContainer(604)
    client.purge_container()
    client.create_container('client-test',
                            image_path,
                            [NetworkInterface(vlan_tag=100)],
                            onboot=1)
    client.update_container()
    # time.sleep(1)
    print(client.get_ip(0))
    print(client.pct_console_shell('uname -a'))

    # dns_master_and_slave(image_path)


def dns_master_and_slave(image_path):
    dns_master = AlpineContainer(605)
    dns_master.purge_container()
    dns_master.create_container('dns-test-master',
                                image_path,
                                # TODO: would be great if NetworkInterface could detect likely IP conflicts
                                [NetworkInterface(vlan_tag=100,
                                                  ip4='10.100.0.5/24',
                                                  gw4='10.100.0.1')],
                                onboot=1)
    dns_master.update_container()
    print(dns_master.get_ip(0))

    dns_slave = AlpineContainer(606)
    dns_slave.purge_container()
    dns_slave.create_container('dns-test-slave',
                               image_path,
                               [NetworkInterface(vlan_tag=100,
                                                 ip4='10.100.0.6/24',
                                                 gw4='10.100.0.1')],
                               onboot=1)
    dns_slave.update_container()
    print(dns_slave.get_ip(0))

    dns_master_service = BindService(dns_master, 'dns master')
    dns_master_service.install_bind_dns_authoritative(dns_master,
                                                      dns_master.network_interfaces[0],
                                                      master_zones=[MasterZone(domain_name='test.lan',
                                                                               slaves=[dns_slave.network_interfaces[
                                                                                           0].ip4.ip])])
    dns_slave_service = BindService(dns_slave, 'dns slave')
    dns_slave_service.install_bind_dns_authoritative(dns_slave,
                                                     dns_slave.network_interfaces[0],
                                                     slave_zones=[SlaveZone(domain_name='test.lan',
                                                                            masters=[dns_master.network_interfaces[
                                                                                         0].ip4.ip])])


if __name__ == '__main__':
    main()
