import lxc.distro.alpine.actions


class NfsServer(lxc.distro.alpine.actions.AlpineService):
    """
    config: /etc/exports
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self):
        self.container.apk_add('nfs-utils')
        self.container.rc_update('nfs', 'add')
        self.container.rc_service('nfs', 'start')

    def add_export(self, nfs_path: str, access_line: str):
        # TODO: not tested
        self.container.append_file('/etc/exports', f'{nfs_path} {access_line}')
        self.container.pct_console_shell('exportfs -arv')


class NfsClient(lxc.distro.alpine.actions.AlpineService):
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
        # mount_persist_reboot is a workaround/alternative for starting the mount service at boot

    def add_mount(self, local_path: str, remote_path: str):
        self.container.append_file('/etc/fstab', f'{remote_path} {local_path} nfs defaults 0 0')
        self.container.pct_console_shell(f'mkdir {local_path}')
        self.container.pct_console_shell('mount -a')

    def mount_persist_reboot(self):
        self.container.rc_update('local', 'add')
        self.container.pct_console_shell(
            'echo "mount -a" > /etc/local.d/mount.start && chmod +x /etc/local.d/mount.start')
