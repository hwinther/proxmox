import lxc.distro.alpine.actions


class GatewayService(lxc.distro.alpine.actions.AlpineService):
    """
    Config /var/lib/transmission/config/settings.json
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self):
        self.container.apk_add('transmission-daemon')
        self.container.apk_add('transmission-cli')

        self.container.rc_update('transmission-daemon', 'add')

        # TODO: firewall policy?

        # TODO: configure service

        self.container.rc_service('transmission-daemon', 'start')
