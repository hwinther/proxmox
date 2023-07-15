from typing import List

import lxc.distro.alpine.actions


class LdapConfig:
    auth_server = None
    ldap_suffix = None
    ldap_admin_dn = None

    def __init__(self, auth_server, ldap_suffix, ldap_admin_dn):
        self.auth_server = auth_server
        self.ldap_suffix = ldap_suffix
        self.ldap_admin_dn = ldap_admin_dn


class SambaShare:
    name: str = None
    path: str = None
    comment: str = None
    create_mask: int = None
    directory_mask: int = None
    valid_users: str = None
    guest_ok: bool = None
    browseable: bool = None
    read_only: bool = None
    printable: bool = None

    def __init__(self, name: str, path: str, comment: str = None,
                 create_mask: int = None, directory_mask: int = None, valid_users: str = None,
                 guest_ok: bool = False, browseable: bool = False, read_only: bool = True, printable: bool = False):
        self.name = name
        self.path = path
        self.comment = comment
        self.create_mask = create_mask
        self.directory_mask = directory_mask
        self.valid_users = valid_users

        self.guest_ok = guest_ok
        self.browseable = browseable
        self.read_only = read_only
        self.printable = printable

    def generate_config_section(self):
        path = f'  path = {self.path}\n' if self.path is not None else ''
        comment = f'  comment = {self.comment}\n' if self.comment is not None else ''
        create_mask = f'  create mask = {self.create_mask}\n' if self.create_mask is not None else ''
        directory_mask = f'  directory mask = {self.directory_mask}\n' if self.directory_mask is not None else ''
        valid_users = f'  valid users = {self.valid_users}\n' if self.valid_users is not None else ''

        guest_ok = 'yes' if self.guest_ok else 'no'
        browseable = 'yes' if self.browseable else 'no'
        read_only = 'yes' if self.read_only else 'no'
        printable = 'yes' if self.printable else 'no'

        return f"""
[{self.name}]
{path}{comment}{create_mask}{directory_mask}{valid_users}  guest ok = {guest_ok}
  browseable = {browseable}
  read only = {read_only}
  printable = {printable}
"""


SAMBA_SHARE_HOMES = SambaShare(name='homes', path='', comment='Home Directories',
                               create_mask=700, directory_mask=700, valid_users='%S',
                               browseable=False, read_only=True)


class SambaService(lxc.distro.alpine.actions.AlpineService):
    """
    Config /etc/samba/smb.conf
    Doc https://www.samba.org/samba/docs/current/man-html/smbclient.1.html
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self, ws: bool = False, mdns: bool = False, domain_master: bool = False, ntlm_support=False,
                ldap_config: LdapConfig = None, shares: List[SambaShare] = None):
        """
        Install the samba service with specified features
        ws - https://en.wikipedia.org/wiki/WS-Discovery
        mdns - https://en.wikipedia.org/wiki/Multicast_DNS
        domain_master - Enable netbios name master role for the interfaces it listens on
        ntlm_support - Enables support for LANMAN/NT4
        ldap_config - LDAP configuration such as suffix and auth server hostname
        shares - List of shares
        """

        # Samba comes with nmbd which makes the shares visible for smb1 clients (such as older versions of windows)
        # TODO: samba-common-tools contains testparm which we can use to verify the configuration
        self.container.apk_add('samba-server samba-common-tools')
        self.container.rc_update('samba', 'add')

        if ws:
            # Add WS discovery support for newer windows clients
            # TODO: check if wsdd is already installed
            self.container.apk_add('wsdd')
            self.container.rc_update('wsdd', 'add')

        if mdns:
            # Add avahi/zeroconf/mDNS for mac and linux clients
            # TODO: check if avahi is already installed
            self.container.apk_add('avahi')
            self.container.rc_update('avahi-daemon', 'add')

        # TODO: firewall policy?

        config_temp_path = '/tmp/smb.conf'
        config_content = open('../templates/samba/smb.conf', 'r').read()

        if domain_master:
            config_content += """
# domain_master start
  domain master = yes
  local master = yes
  preferred master = yes
  dns proxy = no
  wins support = yes
# domain_master end
"""

        if ntlm_support:
            config_content += """
# ntlm_support start
  server min protocol = LANMAN1
  ntlm auth = yes
  lanman auth = yes
# ntlm_support end            
"""

        if ldap_config:
            config_content += """
# ldap_config start
passdb backend = ldapsam:ldap://AUTH_SERVER
ldap suffix = LDAP_SUFFIX
ldap user suffix = ou=People
ldap group suffix = ou=Groups
ldap machine suffix = ou=Computers
ldap idmap suffix = ou=Idmap
ldap admin dn = LDAP_ADMIN_DN
ldap ssl = start tls
ldap passwd sync = yes
# ldap_config end
            """.replace('AUTH_SERVER', ldap_config.auth_server) \
                .replace('LDAP_SUFFIX', ldap_config.ldap_suffix) \
                .replace('LDAP_ADMIN_DN', ldap_config.ldap_admin_dn)

        for share in shares:
            config_content += share.generate_config_section()

        self.container.pct_console_shell('mv /etc/samba/smb.conf /etc/samba/smb.conf.example')
        open(config_temp_path, 'w').write(config_content)

        self.container.push_file('/etc/samba/smb.conf', config_temp_path)

        if mdns:
            # Add samba service to avahi
            config_temp_path = '/tmp/smb.service'
            config_content = open('../templates/avahi/services/smb.service', 'r').read()
            open(config_temp_path, 'w').write(config_content)
            self.container.push_file('/etc/avahi/services/smb.service', config_temp_path)

        self.container.pct_console_shell('testparm -s')  # verify config file(s)
        self.container.rc_service('samba', 'start')

        if ws:
            self.container.rc_service('wsdd', 'start')

        if mdns:
            self.container.rc_service('avahi-daemon', 'start')


class SambaClient(lxc.distro.alpine.actions.AlpineService):
    """
    Config /etc/samba/smb.conf
    """
    container: lxc.distro.alpine.actions.AlpineContainer = None

    def __init__(self, container: lxc.distro.alpine.actions.AlpineContainer, name: str):
        super().__init__(container, name)

    def install(self, wins_server: str = None):
        self.container.apk_add('samba-client')

        # TODO: check if config has created by our samba service before overwriting it
        self.container.pct_console_shell('mv /etc/samba/smb.conf /etc/samba/smb.conf.example')
        config_temp_path = '/tmp/smb.conf'
        config_content = open('../templates/samba/smb.conf', 'r').read()

        if wins_server:
            config_content = config_content.replace(';   wins server = w.x.y.z', f'   wins server = {wins_server}')

        open(config_temp_path, 'w').write(config_content)
        self.container.push_file('/etc/samba/smb.conf', config_temp_path)
