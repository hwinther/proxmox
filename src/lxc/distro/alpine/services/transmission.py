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

    def install(self, download_directory: str, rpc_whitelist: str):
        self.container.apk_add('transmission-daemon transmission-cli')
        self.container.rc_update('transmission-daemon', 'add')

        # TODO: firewall policy?

        # start-stop it once to create the folder structure
        self.container.rc_service('transmission-daemon', 'start')
        self.container.rc_service('transmission-daemon', 'stop')

        self.container.pct_console_shell(
            'mv /var/lib/transmission/config/settings.json /var/lib/transmission/config/settings.json.example')

        # TODO: configure whitelist, username and password for API
        self.container.push_file_from_template(container_file_path='/var/lib/transmission/config/settings.json',
                                               template_file_path='../templates/transmission/settings.json',
                                               DOWNLOAD_DIRECTORY=download_directory,
                                               RPC_WHITELIST=rpc_whitelist)

        self.container.rc_service('transmission-daemon', 'start')
