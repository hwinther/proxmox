import subprocess
from src.lxc.actions import pct_console_shell


def update_container(container_id):
    pct_console_shell(container_id, f"apk update && apk version")
    for i in range(0, 3):
        try:
            pct_console_shell(container_id, f"apk upgrade")
            break
        except subprocess.CalledProcessError as exception:
            if exception.stderr.find(b'temporary error (try again later)') != -1:
                print(f'Temporary error in "apk upgrade", retry #{i+1}')
            else:
                raise


def get_ip(container_id, interface_id):
    # TODO: use generic "ip a" parse method from library here
    ip_output = pct_console_shell(container_id, f"ip a show eth{interface_id}")
    ip4 = None
    ip6 = None
    for line in ip_output.split('\n'):
        if line.find('inet ') != -1:
            ip4 = line.split('inet ')[1].split(' ')[0].split('/')[0]
        elif line.find('inet6 ') != -1:
            ip6 = line.split('inet6 ')[1].split(' ')[0].split('/')[0]
    return ip4, ip6


def apk_add(container_id, package_name):
    # TODO: verify installation, also check if installed first?
    return pct_console_shell(container_id, f"apk add {package_name}")


def rc_update(container_id, service_name, operation):
    # TODO: verify service change, check if it exists first?
    return pct_console_shell(container_id, f"rc-update {operation} {service_name}")


def rc_service(container_id, service_name, operation):
    # TODO: verify service status, check if it exists first?
    return pct_console_shell(container_id, f"rc-service {service_name} {operation}")
