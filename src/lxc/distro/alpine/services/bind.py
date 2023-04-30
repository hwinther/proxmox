from ipaddress import IPv4Address
from typing import Sequence

from lxc.distro.alpine.actions import AlpineService
from lxc.models import NetworkInterface


class DnsZone:
    domain_name: str = None

    def __init__(self, domain_name: str):
        self.domain_name = domain_name

    def get_ips(self) -> Sequence[IPv4Address]:
        raise NotImplementedError('get_ips was not implemented')


class ForwardZone(DnsZone):
    nameservers: Sequence[IPv4Address]

    def __init__(self, domain_name: str, nameservers: Sequence[IPv4Address]):
        super().__init__(domain_name)
        self.nameservers = nameservers

    def get_ips(self) -> Sequence[IPv4Address]:
        return self.nameservers


class MasterZone(DnsZone):
    slaves: Sequence[IPv4Address]

    def __init__(self, domain_name: str, slaves: Sequence[IPv4Address]):
        super().__init__(domain_name)
        self.slaves = slaves

    def get_ips(self) -> Sequence[IPv4Address]:
        return self.slaves


class SlaveZone(DnsZone):
    masters: Sequence[IPv4Address]

    def __init__(self, domain_name: str, masters: Sequence[IPv4Address]):
        super().__init__(domain_name)
        self.masters = masters

    def get_ips(self) -> Sequence[IPv4Address]:
        return self.masters


class BindService(AlpineService):
    """
    /etc/bind - config
    /var/bind - zones/db
      sub directories dyn|pri|sec for specific zone types
    /run/named - state/pid
    """

    def add_bind(self):
        # bind-dnssec-tools is included to create tsig keys for replication or ddns integration
        self.container.apk_add('bind bind-dnssec-tools')
        self.container.rc_update('named', 'add')

    def start_bind(self):
        self.container.rc_service('named', 'start')

    def common_config_rewrite(self,
                              listen_interface: NetworkInterface,
                              file_path: str):
        named_conf_temp_path = '/tmp/named.conf'
        named_template_conf = open(file_path, 'r').read()
        named_template_conf = named_template_conf.replace('1.2.3.0/24', str(listen_interface.ip4.network))
        named_template_conf = named_template_conf.replace('1.2.3.2', str(listen_interface.ip4.ip))
        open(named_conf_temp_path, 'w').write(named_template_conf)
        self.container.push_file('/etc/bind/named.conf', named_conf_temp_path)

    def install_bind_dns_recursive(self,
                                   listen_interface: NetworkInterface):
        self.add_bind()
        self.common_config_rewrite(listen_interface, '../templates/bind9/named.conf.recursive')
        self.start_bind()

    @staticmethod
    def semicolon_join_ips(ips: Sequence[IPv4Address]):
        if len(ips) == 0:
            return ''
        return '; '.join([str(ip) for ip in ips]) + ';'

    def template_and_push(self,
                          source_template: str,
                          container_file_path: str,
                          zones: Sequence[DnsZone]):
        template = open(source_template, 'r').read()
        templates = []
        if zones is None:
            zones = []
        for zone in zones:
            config = template
            config = config.replace('local.lan', zone.domain_name)
            config = config.replace('1.2.3.4;', self.semicolon_join_ips(zone.get_ips()))
            templates.append(config)
        config_temp_path = '/tmp/named.tmp'
        open(config_temp_path, 'w').write('\n'.join(templates))
        self.container.push_file(container_file_path, config_temp_path)

    def install_bind_dns_authoritative(self,
                                       listen_interface: NetworkInterface,
                                       forward_zones: Sequence[ForwardZone] = None,
                                       master_zones: Sequence[MasterZone] = None,
                                       slave_zones: Sequence[SlaveZone] = None):
        self.add_bind()
        self.common_config_rewrite(listen_interface, '../templates/bind9/named.conf.authoritative')
        self.container.pct_console_shell('tsig-keygen tsig-update-key > /etc/bind/named.keys.conf')

        self.template_and_push('../templates/bind9/named.zones.forward.conf',
                               '/etc/bind/named.zones.forward.conf',
                               forward_zones)

        self.template_and_push('../templates/bind9/named.zones.master.conf',
                               '/etc/bind/named.zones.master.conf',
                               master_zones)

        zone_template = open('../templates/bind9/zone.template', 'r').read()
        zone_temp_path = '/tmp/named.zone.tmp'
        if master_zones is None:
            master_zones = []
        for master_zone in master_zones:
            zone = zone_template
            zone = zone.replace('example.com', master_zone.domain_name)
            zone = zone.replace('192.168.254.2', str(listen_interface.ip4.ip))
            open(zone_temp_path, 'w').write(zone)
            self.container.push_file(f'/var/bind/pri/{master_zone.domain_name}', zone_temp_path)

        self.template_and_push('../templates/bind9/named.zones.slave.conf',
                               '/etc/bind/named.zones.slave.conf',
                               slave_zones)

        self.start_bind()
