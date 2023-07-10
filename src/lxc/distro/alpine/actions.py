import subprocess
from typing import List

import lxc.actions


class AlpineService(lxc.actions.Service):
    container: "AlpineContainer" = None

    def __init__(self, container: "AlpineContainer", name: str):
        super().__init__(container, name)
        self.container.services.append(self)


class AlpineContainer(lxc.actions.Container):
    services: List[AlpineService] = None

    def update_container(self):
        if not self.updates_available():
            return

        for i in range(0, 3):
            try:
                self.pct_console_shell(f"apk upgrade")
                break
            except subprocess.CalledProcessError as exception:
                if exception.stderr.find(b'temporary error (try again later)') != -1:
                    print(f'Temporary error in "apk upgrade", retry #{i + 1}')
                else:
                    raise

    def updates_available(self):
        updates = self.apk_update_version()
        updates_lines = list(filter(None, updates.split('Available:\n', 1)[1].split('\n')))
        return len(updates_lines) != 0

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

    def apk_add(self, package_name):
        # TODO: verify installation, also check if installed first?
        return self.pct_console_shell(f"apk add {package_name}")

    def apk_update_version(self):
        return self.pct_console_shell(f"apk update && apk version")

    def rc_update(self, service_name, operation):
        # TODO: verify service change, check if it exists first?
        return self.pct_console_shell(f"rc-update {operation} {service_name}")

    def rc_service(self, service_name, operation):
        # TODO: verify service status, check if it exists first?
        return self.pct_console_shell(f"rc-service {service_name} {operation}")
