from __future__ import annotations

from lxc.distro.alpine.services.jellyfin import JellyfinService
from lxc.distro.alpine.services.msmtp import SmtpService
from lxc.distro.alpine.services.muacme import AcmeService
from lxc.distro.alpine.services.nginx import NginxService
from lxc.distro.alpine.services.transmission import TransmissionService
from lxc.distro.debian.actions import DebianContainer
from src.common.common import config
from src.lxc.actions import Container
from src.lxc.distro.alpine.actions import AlpineContainer
from src.lxc.distro.alpine.services.bind import BindService, MasterZone, SlaveZone
from src.lxc.distro.alpine.services.dhcpd import DhcpService
from src.lxc.distro.alpine.services.gateway import GatewayService
from src.lxc.distro.alpine.services.nfs import NfsClient, NfsServer
from src.lxc.distro.alpine.services.samba import SAMBA_SHARE_HOMES, SambaClient, SambaService
from src.lxc.models import NetworkInterface, Subnet


def main():
    from lxc.actions import update_lxc_templates
    alpine_newest_image_name, debian_newest_image_name = update_lxc_templates()

    # TODO: translate image names not just for local (template_)storage?
    alpine_image_path = f'/var/lib/vz/template/cache/{alpine_newest_image_name}'
    debian_image_path = f'/var/lib/vz/template/cache/{debian_newest_image_name}'

    # TODO: improve lazy caching
    # alpine_image_path = '/var/lib/vz/template/cache/alpine-3.18-default_20230607_amd64.tar.xz'
    # debian_image_path = '/var/lib/vz/template/cache/debian-12-standard_12.2-1_amd64.tar.zst'

    alpine_version = alpine_image_path.split('alpine-')[1].split('-')[0]
    debian_version = debian_image_path.split('-standard_')[1].split('-')[0]

    # for i in range(601, 612):
    # print(f'Purging {i}')
    # Container.purge_container_by_id(i)

    # test_network(image_path)
    # dns_master_and_slave(image_path)
    # samba_server_and_client(image_path)
    # nfs_server_and_client(image_path)
    # transmission(image_path)
    # jellyfin(image_path)

    check_existing_containers(alpine_version, debian_version, update=False)

    # TODO: add NFS server/share to test platform, use this in jellyfin and transmission config
    # TODO: finish unifi setup (also with nginx for ssl?)
    # TODO: add nginx/tighttpd? support for ddnsadmin deployment
    # TODO: add IP/MAC uniqueness checks to avoid conflicts.. either within scope of VLAN or globally?

    # TODO: add ldap server support
    # TODO: add ldap client support
    # TODO: add sssd client config for ldap
    # TODO: krb5 support?


# Borrowed from https://www.geeksforgeeks.org/compare-two-version-numbers/
# Method to compare two versions.
# Return 1 if v2 is smaller,
# -1 if v1 is smaller,
# 0 if equal
def version_compare(v1, v2):
    # This will split both the versions by '.'
    arr1 = v1.split(".")
    arr2 = v2.split(".")
    n = len(arr1)
    m = len(arr2)

    # converts to integer from string
    arr1 = [int(i) for i in arr1]
    # print(arr2)
    arr2 = [int(i) for i in arr2]

    # compares which list is bigger and fills
    # smaller list with zero (for unequal delimiters)
    if n > m:
        for i in range(m, n):
            arr2.append(0)
    elif m > n:
        for i in range(n, m):
            arr1.append(0)

    # returns 1 if version 1 is bigger and -1 if
    # version 2 is bigger and 0 if equal
    for i in range(len(arr1)):
        if arr1[i] > arr2[i]:
            return 1
        elif arr2[i] > arr1[i]:
            return -1
    return 0


def check_existing_containers(alpine_version: str, debian_version: str, update: bool = False):
    containers: list[AlpineContainer | DebianContainer] = []
    # for i in range(601, 605):
    #     containers.append(AlpineContainer(i))
    active_configs = Container.pct_list()
    for lxc_config in active_configs:
        if lxc_config.ostype == 'alpine':
            containers.append(AlpineContainer(lxc_config=lxc_config))
        elif lxc_config.ostype == 'debian':
            containers.append(DebianContainer(lxc_config=lxc_config))
        else:
            print(f'\033[31mUnhandled ostype {lxc_config.ostype} for node {lxc_config.hostname}\033[0m')

    print(f'\033[93mFound: \033[92m{len(containers)}\033[93m active containers\033[0m')

    for container in containers:
        try:
            prefix = f'\033[35m[\033[96m{container.id}\033[35m] '
            release: str = container.pct_get_os_version()

            if isinstance(container, AlpineContainer):
                distro = 'Alpine'
                color = version_compare(alpine_version,
                                        release) <= 0 and '\033[32m(newest)' or f'\033[31m(outdated, newest is {alpine_version})'
            elif isinstance(container, DebianContainer):
                distro = 'Debian'
                color = version_compare(debian_version,
                                        release) <= 0 and '\033[32m(newest)' or f'\033[31m(outdated, newest is {debian_version})'
            else:
                raise NotImplementedError("Unknown container type")

            print(f'\n{prefix}\033[93m{distro}: \033[95m{release} {color}\033[0m')
            uname = container.pct_console_shell("uname -a").strip()
            print(f'{prefix}\033[93mUname: \033[95m{uname}\033[0m')

            updates_available = container.updates_available()
            color = len(updates_available) == 0 and '\033[32m' or '\033[31m'
            amount = len(updates_available)
            print(
                f'{prefix}\033[93mUpdates available for \033[94m{container.lxc_config.hostname}: {color}{amount}\033[0m')

            if not update or not updates_available:
                continue

            print(f'{prefix}\033[91mUpdating..\033[0m')
            container.update_container()
            
        except Exception as e:
            print(f'\033[31m{e}\033[0m')


def test_network(image_path: str):
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


def dns_master_and_slave(image_path: str):
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


def samba_server_and_client(image_path: str):
    # Create samba server
    samba_server = AlpineContainer(606)
    samba_server.purge_container()
    samba_server.create_container('samba-test',
                                  image_path,
                                  [NetworkInterface(mac='C2:25:0C:61:BF:F1',
                                                    ip4='192.168.100.248/24',
                                                    gw4='192.168.100.254')],
                                  onboot=1)
    samba_server.update_container()
    print(samba_server.get_ip(0))

    smtp_service = SmtpService(samba_server, '(m)smtp service')
    smtp_service.install(mail_host='mail.oh.wsh.no', mail_from_host='test.wsh.no', mail_from_name='Samba test')
    smtp_service.test('proxmox@wsh.no')

    acme_service = AcmeService(samba_server, '(mu)acme service')
    # use staging=False for production usage/to get valid SSL
    acme_service.install(acme_email=config.acme_email,
                         ddns_server=config.ddns_server,
                         ddns_tsig_key=config.ddns_tsig_key,
                         staging=True)
    acme_service.issue('samba-test.test.wsh.no', staging=True)

    samba_service = SambaService(samba_server, 'samba/smb service')
    samba_service.install(ws=True, mdns=True, domain_master=True, ntlm_support=True, ldap_config=None,
                          shares=[SAMBA_SHARE_HOMES])

    print(samba_server.pct_console_shell("adduser test; echo 'test:Password1' | chpasswd"))
    print(samba_server.pct_console_shell("echo -ne 'Password1\nPassword1\n' | smbpasswd -a -s test"))

    # TODO: verify connectivity via samba client
    samba_client = AlpineContainer(607)
    samba_client.purge_container()
    samba_client.create_container('samba-test2',
                                  image_path,
                                  [NetworkInterface(mac='C2:25:0C:61:BF:F2',
                                                    ip4='192.168.100.247/24',
                                                    gw4='192.168.100.254')],
                                  onboot=1)
    samba_client.update_container()
    print(samba_client.get_ip(0))

    # configure busybox syslogd to log both locally and to a remote host
    samba_client.pct_console_shell("echo 'SYSLOGD_OPTS=\\\"-t -LR 192.168.100.20:1234\\\"' > /etc/conf.d/syslog")
    samba_client.rc_service('syslog', 'restart')

    samba_client_service = SambaClient(samba_client, 'samba/smb client service')
    samba_client_service.install(wins_server=str(samba_server.network_interfaces[0].ip4.ip))

    print(samba_client.pct_console_shell('smbclient -U test%Password1 -c ls //samba-test/test'))


def nfs_server_and_client(image_path: str):
    # Create nfs server container
    nfs_server = AlpineContainer(609)
    nfs_server.purge_container()
    nfs_server.create_container('nfs-test',
                                image_path,
                                # [NetworkInterface(vlan_tag=100)],
                                [NetworkInterface(mac='C2:25:0C:61:B1:01',
                                                  ip4='192.168.100.245/24',
                                                  gw4='192.168.100.254')],
                                onboot=1,
                                # unprivileged=0,
                                # feature_mount='nfs',
                                # feature_nesting=0,
                                )
    nfs_server.update_container()
    print(nfs_server.get_ip(0))

    nfs_service = NfsServer(nfs_server, 'nfs daemon service')
    nfs_service.install()

    nfs_service.add_export(nfs_path='/tmp', access_line='192.168.100.0/24(ro)')
    nfs_service.container.append_file('/tmp/testfile.txt', 'test content')

    # Create nfs client container
    nfs_client = AlpineContainer(610)
    nfs_client.purge_container()
    nfs_client.create_container('nfs-test2',
                                image_path,
                                # [NetworkInterface(vlan_tag=100)],
                                [NetworkInterface(mac='C2:25:0C:61:B1:02',
                                                  ip4='192.168.100.244/24',
                                                  gw4='192.168.100.254')],
                                onboot=1, unprivileged=0, feature_mount='nfs', feature_nesting=0)
    nfs_client.update_container()
    print(nfs_client.get_ip(0))

    nfs_client_service = NfsClient(nfs_client, 'nfs support service')
    nfs_client_service.install()
    nfs_client_service.add_mount(local_path='/mnt/test', remote_path='192.168.100.245:/tmp', options='nolock')
    print(nfs_client.pct_console_shell('ls -la /mnt/test'))
    nfs_client_service.mount_persist_reboot()


def transmission(image_path: str):
    # Create transmission container
    transmission_server = AlpineContainer(605)
    transmission_server.purge_container()
    transmission_server.create_container('transmission-test',
                                         image_path,
                                         # [NetworkInterface(vlan_tag=100)],
                                         [NetworkInterface(mac='C2:25:0C:61:BF:4C',
                                                           ip4='192.168.100.249/24',
                                                           gw4='192.168.100.254')],
                                         onboot=1, unprivileged=0, feature_mount='nfs', feature_nesting=0)
    transmission_server.update_container()
    print(transmission_server.get_ip(0))

    nfs_client = NfsClient(transmission_server, 'nfs support service')
    nfs_client.install()
    nfs_client.add_mount(local_path='/mnt/Videos', remote_path='192.168.100.28:/mnt/primary/Videos')
    print(transmission_server.pct_console_shell('ls -la /mnt/Videos'))
    nfs_client.mount_persist_reboot()

    transmission_service = TransmissionService(transmission_server, 'transmission service')
    transmission_service.install(download_directory='/mnt/Videos/Downloads', rpc_whitelist='192.168.100.*')

    # TODO: add feed.py to cron ++
    # TODO: perhaps use post trigger in transmission to move files?


def jellyfin(image_path: str):
    # Create jellyfin container
    jellyfin_server = AlpineContainer(608)
    jellyfin_server.purge_container()
    jellyfin_server.create_container('jellyfin-test',
                                     image_path,
                                     # [NetworkInterface(vlan_tag=100)],
                                     [NetworkInterface(mac='C2:25:0C:61:BF:4D',
                                                       ip4='192.168.100.246/24',
                                                       gw4='192.168.100.254')],
                                     onboot=1, unprivileged=0, feature_mount='nfs', feature_nesting=0,
                                     rootfs_size='1', memory=1024)
    jellyfin_server.update_container()
    print(jellyfin_server.get_ip(0))

    nfs_client = NfsClient(jellyfin_server, 'nfs support service')
    nfs_client.install()
    nfs_client.add_mount(local_path='/mnt/Videos', remote_path='192.168.100.28:/mnt/primary/Videos')
    print(jellyfin_server.pct_console_shell('ls -la /mnt/Videos'))
    nfs_client.mount_persist_reboot()

    jellyfin_service = JellyfinService(jellyfin_server, 'jellyfin service')
    jellyfin_service.install()

    # you have to manually configure it via web ui afterwards on http://192.168.100.246:8096
    # TODO: add nginx and muacme
    domain_name = 'jellyfin-test.test.wsh.no'
    zone = 'test.wsh.no'
    staging = False  # use staging=False for production usage/to get valid SSL

    acme_service = AcmeService(jellyfin_server, '(mu)acme service')
    acme_service.install(acme_email=config.acme_email,
                         ddns_server=config.ddns_server,
                         ddns_tsig_key=config.ddns_tsig_key,
                         staging=staging)
    acme_service.issue(domain_name=domain_name, staging=staging)
    # TODO: we add the name, but it is never removed later on
    acme_service.ddns_update(operation='add',
                             ddns_server=config.ddns_server,
                             ddns_tsig_key=config.ddns_tsig_key,
                             ddns_zone=zone,
                             domain_name=domain_name,
                             ip=str(jellyfin_server.network_interfaces[0].ip4.ip))

    nginx_service = NginxService(jellyfin_server, 'nginx service')
    nginx_service.install(domain_name=domain_name)

    print(jellyfin_server.pct_console_shell('netstat -anp'))


if __name__ == '__main__':
    main()
