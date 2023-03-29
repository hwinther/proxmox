from src.lxc.actions import pct_console_shell, push_file
from src.lxc.distro.alpine.actions import apk_add, rc_service, rc_update


def install_gateway_nat(container_id):
    apk_add(container_id, 'ip6tables')
    apk_add(container_id, 'awall')

    rc_update(container_id, 'iptables', 'add')
    rc_update(container_id, 'ip6tables', 'add')

    # /etc/awall/optional/ - inactive config folder

    awall_policy_temp_path = '/tmp/gateway-nat-policy.json'
    dhcpd_conf = open('../templates/awall/gateway-nat-policy.json', 'r').read()
    open(awall_policy_temp_path, 'w').write(dhcpd_conf)
    push_file(container_id, '/etc/awall/optional/gateway-nat-policy.json', awall_policy_temp_path)

    # Enable and activate firewall rules
    pct_console_shell(container_id, "awall enable gateway-nat-policy && awall activate -f")

    # Enable routing via sysctl, in the future perhaps also enable ipv6 forwarding?
    pct_console_shell(container_id, "sysctl -w net.ipv4.ip_forward=1")

    rc_service(container_id, 'iptables', 'start')
    rc_service(container_id, 'ip6tables', 'start')
