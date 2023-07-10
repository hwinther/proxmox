import lxc.distro.alpine.actions


class SambaService(lxc.distro.alpine.actions.AlpineService):
    """
    Config /etc/samba/smb.conf
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self):
        # Samba comes with nmbd which makes the shares visible for smb1 clients (such as older versions of windows)
        self.container.apk_add('samba-server')
        self.container.rc_update('samba', 'add')

        # Add WS discovery support for newer windows clients
        self.container.apk_add('wsdd')
        self.container.rc_update('wsdd', 'add')

        # Add avahi/zeroconf/mDNS for mac and linux clients
        self.container.apk_add('avahi')
        self.container.rc_update('avahi-daemon', 'add')

        # TODO: firewall policy?

        config_temp_path = '/tmp/smb.conf'
        config_content = open('../templates/samba/smb.conf', 'r').read()
        open(config_temp_path, 'w').write(config_content)
        self.container.push_file('/etc/samba/smb.conf', config_temp_path)

        # Add samba service to avahi
        config_temp_path = '/tmp/smb.service'
        config_content = open('../templates/avahi/services/smb.service', 'r').read()
        open(config_temp_path, 'w').write(config_content)
        self.container.push_file('/etc/avahi/services/smb.service', config_temp_path)

        self.container.rc_service('samba', 'start')
        self.container.rc_service('wsdd', 'start')
        self.container.rc_service('avahi-daemon', 'start')
