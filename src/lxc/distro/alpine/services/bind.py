import src.lxc.distro.alpine.actions


def install_bind_dns(container: src.lxc.distro.alpine.actions.AlpineContainer, subnet: str):
    # /etc/bind - config
    # /var/bind - zones/db
    #   sub directories dyn|pri|sec for specific zone types
    # /run/named - state/pid

    container.apk_add('bind')
    container.rc_update('named', 'add')

    named_conf_temp_path = '/tmp/named.conf'
    named_conf = open('../templates/bind9/named.conf.recursive', 'r').read()
    named_conf = named_conf.replace('1.2.3', subnet)
    open(named_conf_temp_path, 'w').write(named_conf)
    container.push_file('/etc/bind/named.conf', named_conf_temp_path)

    container.rc_service('named', 'start')
