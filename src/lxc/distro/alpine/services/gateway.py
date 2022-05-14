import lxc.distro.alpine.actions


class GatewayService(lxc.distro.alpine.actions.AlpineService):
    """
    /etc/awall/optional/ - inactive config folder
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self):
        self.container.apk_add('ip6tables awall')
        self.container.rc_update('iptables', 'add')
        self.container.rc_update('ip6tables', 'add')

        self.container.push_file_from_template(container_file_path='/etc/awall/optional/gateway-nat-policy.json',
                                               template_file_path='../templates/awall/gateway-nat-policy.json')

        # Enable and activate firewall rules
        self.container.pct_console_shell("awall enable gateway-nat-policy && awall activate -f")

        # Enable routing via sysctl, in the future perhaps also enable ipv6 forwarding?
        self.container.pct_console_shell("echo \"net.ipv4.ip_forward=1\" >> /etc/sysctl.conf")
        self.container.pct_console_shell("sysctl -p")
        self.container.rc_update('sysctl', 'add')

        self.container.rc_service('iptables', 'start')
        self.container.rc_service('ip6tables', 'start')
