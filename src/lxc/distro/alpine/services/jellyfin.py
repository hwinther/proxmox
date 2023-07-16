import lxc.distro.alpine.actions


class JellyfinService(lxc.distro.alpine.actions.AlpineService):
    """
    config: /etc/conf.d/jellyfin
    https://jellyfin.org/docs/general/installation/linux/#alpine-linux
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self):
        self.container.apk_add('jellyfin jellyfin-web')
        self.container.rc_update('jellyfin', 'add')

        # enable the web ui (it is disabled by default)
        self.container.pct_console_shell("sed -i 's/--nowebclient//' /etc/conf.d/jellyfin")

        self.container.rc_service('jellyfin', 'start')
