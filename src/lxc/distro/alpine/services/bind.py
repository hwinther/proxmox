import src.lxc.distro.alpine.actions
from lxc.models import NetworkInterface


def install_bind_dns_recursive(container: src.lxc.distro.alpine.actions.AlpineContainer,
                               listen_interface: NetworkInterface):
    # /etc/bind - config
    # /var/bind - zones/db
    #   sub directories dyn|pri|sec for specific zone types
    # /run/named - state/pid

    container.apk_add('bind')
    container.rc_update('named', 'add')

    named_conf_temp_path = '/tmp/named.conf'
    named_template_conf = open('../templates/bind9/named.conf.recursive', 'r').read()
    named_template_conf = named_template_conf.replace('1.2.3.0/24', str(listen_interface.ip4.network))
    named_template_conf = named_template_conf.replace('1.2.3.2', str(listen_interface.ip4.ip))
    open(named_conf_temp_path, 'w').write(named_template_conf)
    container.push_file('/etc/bind/named.conf', named_conf_temp_path)

    container.rc_service('named', 'start')
