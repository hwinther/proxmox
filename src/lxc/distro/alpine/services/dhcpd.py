from typing import Sequence

import src.lxc.models
from src.lxc.actions import push_file
from src.lxc.distro.alpine.actions import apk_add, rc_service, rc_update


def install_isc_dhcpd(container_id: int,
                      ip4_subnets: Sequence[src.lxc.models.Subnet],
                      ip4_devices: Sequence[src.lxc.models.Device]):
    """
    Install, configure and start ISC DHCP daemon
    @param container_id: Container/LXC ID
    @param ip4_subnets: Subnet definitions
    @param ip4_devices: Device definitions
    """
    # /etc/dhcp - config
    # /var/lib/dhcp - leases/db
    # /run/dhcp - state/pid

    apk_add(container_id, 'dhcp-server-vanilla')
    rc_update(container_id, 'dhcpd', 'add')

    dhcpd_conf_temp_path = '/tmp/dhcpd.conf'
    dhcpd_conf = open('../templates/isc-dhcp-server/dhcpd.conf', 'r').read()
    open(dhcpd_conf_temp_path, 'w').write(dhcpd_conf)
    push_file(container_id, '/etc/dhcp/dhcpd.conf', dhcpd_conf_temp_path)

    subnets_temp_path = '/tmp/dhcpd.subnets.conf'
    subnets_template_conf = open('../templates/isc-dhcp-server/dhcpd.subnets.conf', 'r').read()
    subnet_configs = []
    for ip4_subnet in ip4_subnets:
        subnet_config = subnets_template_conf
        subnet_config = subnet_config.replace('1.2.3.0', str(ip4_subnet.network.network_address))
        subnet_config = subnet_config.replace('255.255.255.0', str(ip4_subnet.network.netmask))
        subnet_config = subnet_config.replace('1.2.3.100', str(ip4_subnet.range_start))
        subnet_config = subnet_config.replace('1.2.3.200', str(ip4_subnet.range_end))
        subnet_config = subnet_config.replace('1.2.3.1', str(ip4_subnet.router))
        subnet_config = subnet_config.replace('local.lan', ip4_subnet.domain_name)
        if ip4_subnet.domain_name_servers:
            subnet_config = subnet_config.replace('1.2.3.2',
                                                  ', '.join([str(ip) for ip in ip4_subnet.domain_name_servers]))
            subnet_config = subnet_config.replace('# option domain-name-servers',
                                                  'option domain-name-servers')
        if ip4_subnet.netbios_name_servers:
            subnet_config = subnet_config.replace('1.2.3.3',
                                                  ', '.join([str(ip) for ip in ip4_subnet.netbios_name_servers]))
            subnet_config = subnet_config.replace('# option netbios-name-servers',
                                                  'option netbios-name-servers')
        if ip4_subnet.ntp_servers:
            subnet_config = subnet_config.replace('1.2.3.4',
                                                  ', '.join([str(ip) for ip in ip4_subnet.ntp_servers]))
            subnet_config = subnet_config.replace('# option ntp-servers',
                                                  'option ntp-servers')
        subnet_configs.append(subnet_config)
    open(subnets_temp_path, 'w').write('\n'.join(subnet_configs))
    push_file(container_id, '/etc/dhcp/dhcpd.subnets.conf', subnets_temp_path)

    devices_temp_path = '/tmp/dhcpd.devices.conf'
    devices_template_conf = open('../templates/isc-dhcp-server/dhcpd.devices.conf', 'r').read()
    device_configs = []
    for ip4_device in ip4_devices:
        device_config = devices_template_conf
        device_config = device_config.replace('host.local.lan', ip4_device.hostname)
        device_config = device_config.replace('00:11:22:33:44:55', ip4_device.hardware_ethernet)
        device_config = device_config.replace('1.2.3.4', str(ip4_device.fixed_address))
        device_configs.append(device_config)
    open(devices_temp_path, 'w').write('\n'.join(device_configs))
    push_file(container_id, '/etc/dhcp/dhcpd.devices.conf', devices_temp_path)

    rc_service(container_id, 'dhcpd', 'start')
