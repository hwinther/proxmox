from pathlib import Path
from typing import Sequence

import lxc.distro.alpine.actions
import lxc.models


class DhcpService(lxc.distro.alpine.actions.AlpineService):
    """
    /etc/dhcp - config
    /var/lib/dhcp - leases/db
    /run/dhcp - state/pid
    """

    def install(self,
                ip4_subnets: Sequence[lxc.models.Subnet],
                ip4_devices: Sequence[lxc.models.Device]):
        """
        Install, configure and start ISC DHCP daemon
        @param ip4_subnets: Subnet definitions
        @param ip4_devices: Device definitions
        """

        self.container.apk_add('dhcp-server-vanilla')
        self.container.rc_update('dhcpd', 'add')

        dhcpd_conf_temp_path = '/tmp/dhcpd.conf'
        dhcpd_conf = Path('../templates/isc-dhcp-server/dhcpd.conf').read_text(encoding='utf-8')
        Path(dhcpd_conf_temp_path).write_text(dhcpd_conf, encoding='utf-8')
        self.container.push_file('/etc/dhcp/dhcpd.conf', dhcpd_conf_temp_path)

        subnets_temp_path = '/tmp/dhcpd.subnets.conf'
        subnets_template_conf = Path('../templates/isc-dhcp-server/dhcpd.subnets.conf').read_text(encoding='utf-8')
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
        Path(subnets_temp_path).write_text('\n'.join(subnet_configs), encoding='utf-8')
        self.container.push_file('/etc/dhcp/dhcpd.subnets.conf', subnets_temp_path)

        devices_temp_path = '/tmp/dhcpd.devices.conf'
        devices_template_conf = Path('../templates/isc-dhcp-server/dhcpd.devices.conf').read_text(encoding='utf-8')
        device_configs = []
        for ip4_device in ip4_devices:
            device_config = devices_template_conf
            device_config = device_config.replace('host.local.lan', ip4_device.hostname)
            device_config = device_config.replace('00:11:22:33:44:55', ip4_device.hardware_ethernet)
            device_config = device_config.replace('1.2.3.4', str(ip4_device.fixed_address))
            device_configs.append(device_config)
        Path(devices_temp_path).write_text('\n'.join(device_configs), encoding='utf-8')
        self.container.push_file('/etc/dhcp/dhcpd.devices.conf', devices_temp_path)

        self.container.rc_service('dhcpd', 'start')
