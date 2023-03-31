import src.lxc.distro.alpine.actions
from lxc.distro.alpine.service import AlpineService


class GatewayService(AlpineService):
    """
    /etc/awall/optional/ - inactive config folder
    """
    container: src.lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: src.lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self):
        self.container.apk_add('ip6tables')
        self.container.apk_add('awall')

        self.container.rc_update('iptables', 'add')
        self.container.rc_update('ip6tables', 'add')

        awall_policy_temp_path = '/tmp/gateway-nat-policy.json'
        dhcpd_conf = open('../templates/awall/gateway-nat-policy.json', 'r').read()
        open(awall_policy_temp_path, 'w').write(dhcpd_conf)
        self.container.push_file('/etc/awall/optional/gateway-nat-policy.json', awall_policy_temp_path)

        # Enable and activate firewall rules
        self.container.pct_console_shell("awall enable gateway-nat-policy && awall activate -f")

        # Enable routing via sysctl, in the future perhaps also enable ipv6 forwarding?
        self.container.pct_console_shell("echo \"net.ipv4.ip_forward=1\" >> /etc/sysctl.conf")
        self.container.pct_console_shell("sysctl -p")

        self.container.rc_service('iptables', 'start')
        self.container.rc_service('ip6tables', 'start')
