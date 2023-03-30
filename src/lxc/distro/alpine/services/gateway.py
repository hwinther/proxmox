import src.lxc.distro.alpine.actions


def install_gateway_nat(container: src.lxc.distro.alpine.actions.AlpineContainer):
    # /etc/awall/optional/ - inactive config folder

    container.apk_add('ip6tables')
    container.apk_add('awall')

    container.rc_update('iptables', 'add')
    container.rc_update('ip6tables', 'add')

    awall_policy_temp_path = '/tmp/gateway-nat-policy.json'
    dhcpd_conf = open('../templates/awall/gateway-nat-policy.json', 'r').read()
    open(awall_policy_temp_path, 'w').write(dhcpd_conf)
    container.push_file('/etc/awall/optional/gateway-nat-policy.json', awall_policy_temp_path)

    # Enable and activate firewall rules
    container.pct_console_shell("awall enable gateway-nat-policy && awall activate -f")

    # Enable routing via sysctl, in the future perhaps also enable ipv6 forwarding?
    container.pct_console_shell("echo \"net.ipv4.ip_forward=1\" >> /etc/sysctl.conf")
    container.pct_console_shell("sysctl -p")

    container.rc_service('iptables', 'start')
    container.rc_service('ip6tables', 'start')
