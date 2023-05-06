import lxc.distro.alpine.actions


class JellyfinService(lxc.distro.alpine.actions.AlpineService):
    """
    TODO
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self):
        pass
