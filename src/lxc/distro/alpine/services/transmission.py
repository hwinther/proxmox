import time

import lxc.distro.alpine.actions


class TransmissionService(lxc.distro.alpine.actions.AlpineService):
    """
    Config /var/lib/transmission/config/settings.json
    https://github.com/transmission/transmission/blob/main/docs/Headless-Usage.md
    Should firewall also:
    https://wiki.alpinelinux.org/wiki/How-To_Alpine_Wall#Example_firewall_using_Shorewall
    https://github.com/alpinelinux/awall
    https://www.zsiegel.com/2022/01/13/configuring-alpine-linux-firewall-with-docker
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
        self.container.pct_console_shell(
            'mv /var/lib/transmission/config/settings.json /var/lib/transmission/config/settings.json.example')
        self.container.push_file('/var/lib/transmission/config/settings.json', config_temp_path)

        self.container.rc_service('transmission-daemon', 'start')
