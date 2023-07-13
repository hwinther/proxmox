from src.lxc.actions import Container
from src.lxc.distro.alpine.actions import AlpineContainer
from src.lxc.distro.alpine.services.bind import BindService, MasterZone, SlaveZone
from src.lxc.distro.alpine.services.dhcpd import DhcpService
from src.lxc.distro.alpine.services.gateway import GatewayService
from src.lxc.distro.alpine.services.nfs import NfsService
from src.lxc.distro.alpine.services.samba import SAMBA_SHARE_HOMES, SambaService
from src.lxc.models import NetworkInterface, Subnet


def main():
    # from lxc.actions import update_lxc_templates
    # alpine_newest_image_name = update_lxc_templates()
    # TODO: translate image names not just for local (template_)storage?
    # image_path = f'/var/lib/vz/template/cache/{alpine_newest_image_name}'
    # TODO: improve lazy caching
    image_path = '/var/lib/vz/template/cache/alpine-3.18-default_20230607_amd64.tar.xz'

    # for i in range(601, 607):
    #     print(i)
    #     Container.purge_container_by_id(i)
    #
    # return

    # test_network(image_path)
    # dns_master_and_slave(image_path)
    test_new_services(image_path)
    # check_existing_containers()


def check_existing_containers():
    containers = []
    # for i in range(601, 605):
    #     containers.append(AlpineContainer(i))
    active_configs = Container.pct_list()
    for lxc_config in active_configs:
        if lxc_config.ostype == 'alpine':
            containers.append(AlpineContainer(lxc_config=lxc_config))
        else:
            print(f'Unhandled ostype {lxc_config.ostype} for node {lxc_config.hostname}')

    print(f'Found {len(containers)} active containers')

    for container in containers:
        print(container.pct_console_shell('cat /etc/alpine-release && uname -a').strip())
        print(f'Updates available for {container.lxc_config.hostname}? {container.updates_available()}')


def test_network(image_path):
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
    dns_master_service.install_bind_dns_authoritative(dns_master.network_interfaces[0],
                                                      master_zones=[MasterZone(domain_name='test.lan',
                                                                               slaves=[dns_slave.network_interfaces[
                                                                                           0].ip4.ip])])
    dns_slave_service = BindService(dns_slave, 'dns slave')
    dns_slave_service.install_bind_dns_authoritative(dns_slave.network_interfaces[0],
                                                     slave_zones=[SlaveZone(domain_name='test.lan',
                                                                            masters=[dns_master.network_interfaces[
                                                                                         0].ip4.ip])])


def test_new_services(image_path):
    # Create samba server
    samba_server = AlpineContainer(606)
    samba_server.purge_container()
    samba_server.create_container('samba-test',
                                  image_path,
                                  [NetworkInterface(mac='C2:25:0C:61:BF:F1',
                                                    ip4='10.20.1.248/24',
                                                    gw4='10.20.1.254')],
                                  onboot=1)
    samba_server.update_container()
    print(samba_server.get_ip(0))
    samba_service = SambaService(samba_server, 'samba/smb service')
    samba_service.install(ws=True, mdns=True, domain_master=False, ntlm_support=True, ldap_config=None,
                          shares=[SAMBA_SHARE_HOMES])

    print(samba_server.pct_console_shell('testparm -s'))
    print(samba_server.pct_console_shell("adduser test; echo 'test:Password1' | chpasswd"))
    print(samba_server.pct_console_shell("echo -ne 'Password1\nPassword1\n' | smbpasswd -a -s test"))
    # TODO: verify connectivity via samba client

    return

    # Create transmission container
    transmission_server = AlpineContainer(605)
    transmission_server.purge_container()
    transmission_server.create_container('transmission-test',
                                         image_path,
                                         # [NetworkInterface(vlan_tag=100)],
                                         [NetworkInterface(mac='C2:25:0C:61:BF:4C',
                                                           ip4='10.20.1.249/24',
                                                           gw4='10.20.1.254')],
                                         onboot=1, unprivileged=0, feature_mount='nfs', feature_nesting=0)
    transmission_server.update_container()
    print(transmission_server.get_ip(0))
    # print(transmission_server.pct_console_shell('ping -c 1 10.20.1.28'))
    nfs_service = NfsService(transmission_server, 'nfs support service')
    nfs_service.install()
    transmission_server.append_file('/etc/fstab', '10.20.1.28:/mnt/primary/Videos /mnt/Videos nfs defaults 0 0')
    print(transmission_server.pct_console_shell('mkdir /mnt/Videos'))
    print(transmission_server.pct_console_shell('mount -a'))
    print(transmission_server.pct_console_shell('ls -la /mnt/Videos'))

    # to persist reboot:
    print(transmission_server.rc_update('local', 'add'))
    print(transmission_server.pct_console_shell(
        'echo "mount -a" > /etc/local.d/mount.start && chmod +x /etc/local.d/mount.start'))
    # rc-update add local default
    # echo "mount -a" > /etc/local.d/mount.start
    # chmod +x /etc/local.d/mount.start

    # transmission_service = TransmissionService(transmission_server, 'transmission service')
    # transmission_service.install()


if __name__ == '__main__':
    main()
