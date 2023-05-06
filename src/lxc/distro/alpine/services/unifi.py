import lxc.distro.alpine.actions


class UnifiService(lxc.distro.alpine.actions.AlpineService):
    """
    TODO
    https://wiki.alpinelinux.org/wiki/UniFi_Controller
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self):
        pass
