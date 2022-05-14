import subprocess
from typing import List

import lxc.actions


class DebianService(lxc.actions.Service):
    container: "DebianContainer" = None

    def __init__(self, container: "DebianContainer", name: str):
        super().__init__(container, name)
        self.container.services.append(self)


class DebianContainer(lxc.actions.Container):
    services: List[DebianService] = None

    def update_container(self):
        if not self.updates_available():
            return

        for i in range(0, 3):
            try:
                self.pct_console_shell(f'DEBIAN_FRONTEND=noninteractive apt ' +
                                       '-o "Apt::Cmd::Disable-Script-Warning=true" ' +
                                       '-o "Dpkg::Options::="--force-confold""' +
                                       ' -y full-upgrade')
                break
            except subprocess.CalledProcessError as exception:
                if exception.stderr.find(b'temporary error (try again later)') != -1:
                    print(f'Temporary error in "apt full-upgrade", retry #{i + 1}')
                else:
                    raise

    def updates_available(self):
        updates = self.apt_update_and_list_upgradable()
        updates_lines = list(filter(None, updates.split('Listing...\n', 1)[1].split('\n')))
        return updates_lines

    def get_ip(self, interface_id):
        # TODO: use generic "ip a" parse method from library here
        ip_output = self.pct_console_shell(f"ip a show eth{interface_id}")
        ip4 = None
        ip6 = None
        for line in ip_output.split('\n'):
            if line.find('inet ') != -1:
                ip4 = line.split('inet ')[1].split(' ')[0].split('/')[0]
            elif line.find('inet6 ') != -1:
                ip6 = line.split('inet6 ')[1].split(' ')[0].split('/')[0]
        return ip4, ip6

    def apt_add(self, package_name):
        # TODO: verify installation, also check if installed first?
        return self.pct_console_shell(f'DEBIAN_FRONTEND=noninteractive apt ' +
                                      '-o "Apt::Cmd::Disable-Script-Warning=true" ' +
                                      'install -y {package_name}')

    def apt_update_and_list_upgradable(self):
        # TODO: apk update also times out sometimes
        return self.pct_console_shell(f'apt -o "Apt::Cmd::Disable-Script-Warning=true" update && ' +
                                      'apt -o "Apt::Cmd::Disable-Script-Warning=true" list --upgradable')

    def systemctl(self, service_name, operation):
        # TODO: verify service change, check if it exists first?
        return self.pct_console_shell(f"systemctl {operation} {service_name}")

    def pct_get_os_version(self):
        return self.pct_console_shell('cat /etc/debian_version').strip()
