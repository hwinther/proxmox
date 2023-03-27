from src.lxc.actions import push_file
from src.lxc.distro.alpine.actions import apk_add, rc_update, rc_service


def install_bind_dns(container_id, subnet):
    apk_add(container_id, 'bind')
    rc_update(container_id, 'named', 'add')

    # /etc/bind - config
    # /var/bind - zones/db
    #   sub directories dyn|pri|sec for specific zone types
    # /run/named - state/pid

    named_conf_temp_path = '/tmp/named.conf'
    named_conf = open('../templates/bind9/named.conf.recursive', 'r').read()
    named_conf = named_conf.replace('1.2.3', subnet)
    open(named_conf_temp_path, 'w').write(named_conf)
    push_file(container_id, '/etc/bind/named.conf', named_conf_temp_path)

    rc_service(container_id, 'named', 'start')
