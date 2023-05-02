import time

import lxc.distro.alpine.actions


class TransmissionService(lxc.distro.alpine.actions.AlpineService):
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

        # start-stop it once to create the folder structure
        self.container.rc_service('transmission-daemon', 'start')
        self.container.rc_service('transmission-daemon', 'stop')

        config_temp_path = '/tmp/settings.json'
        # TODO: configure whitelist, username and password for API
        config_content = open('../templates/transmission/settings.json', 'r').read()
        open(config_temp_path, 'w').write(config_content)
        self.container.push_file('/var/lib/transmission/config/settings.json', config_temp_path)

        self.container.rc_service('transmission-daemon', 'start')
