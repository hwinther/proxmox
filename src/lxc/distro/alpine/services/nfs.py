import lxc.distro.alpine.actions


class NfsService(lxc.distro.alpine.actions.AlpineService):
    """
    config: /etc/fstab
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self):
        self.container.apk_add('nfs-utils')

        # client should only need these two, and even they do not seem required:
        # self.container.rc_update('nfsmount', 'add')
        # print(self.container.rc_service('nfsmount', 'start'))

        # daemon would require this
        # self.container.rc_update('nfs', 'add')
        # self.container.rc_service('nfs', 'start')
