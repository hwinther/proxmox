class NetworkInterface:
    vlan_tag = None
    firewall = True
    bridge = None
    ip4 = None
    gw4 = None
    ip6 = None
    gw6 = None

    def __init__(self, vlan_tag=None, firewall=True, bridge=None, ip4=None, gw4=None, ip6=None, gw6=None):
        self.vlan_tag = vlan_tag
        self.firewall = firewall
        self.bridge = bridge
        self.ip4 = ip4
        self.gw4 = gw4
        self.ip6 = ip6
        self.gw6 = gw6
