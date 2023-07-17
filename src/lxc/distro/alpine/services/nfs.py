import lxc.distro.alpine.actions


class NfsServer(lxc.distro.alpine.actions.AlpineService):
    """
    config: /etc/exports
    https://linux.die.net/man/5/exports
    https://github.com/unfs3/unfs3
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self):
        # nfs-util / nfs-openrc service is not supported by PVE
        # see https://forum.proxmox.com/threads/nfs-share-from-lxc.65158/ for details
        self.container.apk_add('rpcbind unfs3')
        self.container.rc_update('rpcbind', 'add')
        self.container.rc_update('unfs3', 'add')
        self.container.rc_service('unfs3', 'start')

    def add_export(self, nfs_path: str, access_line: str):
        """
        Add NFS export
        @param nfs_path: nfs share path, e.g. /share
        @param access_line: access line(s), e.g. 10.0.0.1(ro)[ ..]
        @return:
        """
        self.container.append_file('/etc/exports', f'{nfs_path} {access_line}')
        self.container.pct_console_shell('unfsd -T')
        self.container.rc_service('unfs3', 'restart')


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

    def add_mount(self, local_path: str, remote_path: str, options: str = None):
        options = '' if options is None else ',' + options
        self.container.append_file('/etc/fstab', f'{remote_path} {local_path} nfs defaults{options} 0 0')
        self.container.pct_console_shell(f'mkdir {local_path}')
        self.container.pct_console_shell('mount -a')

    def mount_persist_reboot(self):
        self.container.rc_update('local', 'add')
        self.container.pct_console_shell(
            'echo "mount -a" > /etc/local.d/mount.start && chmod +x /etc/local.d/mount.start')
