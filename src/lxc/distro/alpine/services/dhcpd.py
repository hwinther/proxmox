from src.lxc.actions import push_file
from src.lxc.distro.alpine.actions import apk_add, rc_update, rc_service


def install_isc_dhcpd(container_id, subnet):
    apk_add(container_id, 'dhcp-server-vanilla')
    rc_update(container_id, 'dhcpd', 'add')

    # /etc/dhcp - config
    # /var/lib/dhcp - leases/db
    # /run/dhcp - state/pid

    dhcpd_conf_temp_path = '/tmp/dhcpd.conf'
    dhcpd_conf = open('../templates/isc-dhcp-server/dhcpd.conf', 'r').read()
    open(dhcpd_conf_temp_path, 'w').write(dhcpd_conf)
    push_file(container_id, '/etc/dhcp/dhcpd.conf', dhcpd_conf_temp_path)

    dhcpd_conf_temp_path = '/tmp/dhcpd.subnets.conf'
    dhcpd_conf = open('../templates/isc-dhcp-server/dhcpd.subnets.conf', 'r').read()
    dhcpd_conf = dhcpd_conf.replace('1.2.3', subnet)
    open(dhcpd_conf_temp_path, 'w').write(dhcpd_conf)
    push_file(container_id, '/etc/dhcp/dhcpd.subnets.conf', dhcpd_conf_temp_path)

    dhcpd_conf_temp_path = '/tmp/dhcpd.devices.conf'
    dhcpd_conf = open('../templates/isc-dhcp-server/dhcpd.devices.conf', 'r').read()
    open(dhcpd_conf_temp_path, 'w').write(dhcpd_conf)
    push_file(container_id, '/etc/dhcp/dhcpd.devices.conf', dhcpd_conf_temp_path)

    rc_service(container_id, 'dhcpd', 'start')
    