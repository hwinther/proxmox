import os
import subprocess
import secrets
import string
import time


def generate_random_password(length):
    alphabet = string.ascii_letters + string.digits  # + string.punctuation
    password = ''
    for i in range(length):
        password += ''.join(secrets.choice(alphabet))
    return password


# TODO: move config to separate file and only have sample in repo
# PVE storage, local, local_zfs
storage = 'local'
# container_root_password = lambda: 'static_and_less_safe_password'
container_root_password = lambda: generate_random_password(32)
container_ssh_authorized_key = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGzYkv5+lko9E5Tpc3wHg1ZDm4DZDo/ahtljV3xfiHhf ed25519-key-20171113'
container_ssh_authorized_key_filename = '/tmp/container_ssh_authorized_key'
network_bridge = 'vmbr0'
# TODO: VLAN support
resource_pool = 'Testing'
cpu_cores = 2
memory = 128
swap = 128
verbose = False


def os_exec(cmd, env=None, **kwargs):
    if verbose:
        print(f'executing: {cmd}')
    if 'shell' in kwargs:
        cmds = cmd
    else:
        cmds = cmd.split(' ')
    process = subprocess.run(cmds, capture_output=True, env=env, **kwargs)
    stderr = process.stderr.decode('utf-8')
    if stderr != '':
        print(f'stderr: {stderr}')
    process.check_returncode()
    stdout = process.stdout.decode('utf-8')
    if verbose and stdout != '':
        print(f'stdout: {stdout}')
    return stdout


def update_lxc_templates():
    print('Updating pveam image list')
    os_exec('pveam update')

    alpine_newest = None
    for line in os_exec('pveam available --section system').split('\n'):
        if line.find('alpine-3') != -1:
            alpine_newest = line.replace('system', '').strip()
    if verbose:
        print(f'Newest alpine image: {alpine_newest}')

    alpine_newest_exists = os_exec(f'pveam list {storage}').find(alpine_newest) != -1
    if alpine_newest_exists:
        if verbose:
            print(f'Storage "{storage}" contains the image already.')
    else:
        print(f'Downloading newest alpine image to storage "{storage}"')
        os_exec(f'pveam download {storage} {alpine_newest}')

    return alpine_newest


def purge_container(container_id):
    # TODO: check pct list to see if id exists, then use configured option to determine if we're overwriting it or not
    os_exec(f'(pct stop {container_id}; pct destroy {container_id}); echo 0', shell=True)


def generate_net_argument(interface_id, vlan_tag=None, ip4=None, ip6=None):
    vlan_arg = ''
    if vlan_tag is not None:
        vlan_arg = f'tag={vlan_tag},'
    if ip4 is None:
        ip4 = 'dhcp'
    if ip6 is None:
        ip6 = 'auto'
    return f'--net{interface_id} name=eth{interface_id},bridge={network_bridge},ip={ip4},ip6={ip6},' \
           f'{vlan_arg}firewall=1,type=veth'


def create_container(container_id, container_name, container_image_path, network_interfaces):
    open(container_ssh_authorized_key_filename, 'w').write(container_ssh_authorized_key)

    network_arguments = []
    network_id = 0
    for network_interface in network_interfaces:
        network_arguments.append(generate_net_argument(network_id,
                                                       network_interface.vlan_tag,
                                                       network_interface.ip4,
                                                       network_interface.ip6))
        network_id += 1

    cmd = f'pct create {container_id} {container_image_path} --hostname {container_name}' \
          f' --memory {memory} --swap {swap}' \
          f' --storage {storage} --rootfs local:0.1' \
          f' --unprivileged 1 --pool {resource_pool} --ssh-public-keys {container_ssh_authorized_key_filename}' \
          f' --ostype alpine --password="ROOT_PASSWORD" --cmode shell --cores {cpu_cores} --start 1 ' \
          + ' '.join(network_arguments)
    # f' --mp0 volume={storage}:0.01,mp=/etc/testconfig,backup=1,ro=0,shared=0'
    # TODO: implement storage configuration
    env = os.environ.copy()
    ct_root_pw = container_root_password()
    env['ROOT_PASSWORD'] = ct_root_pw

    os_exec(cmd, env)
    # TODO: verify that it runs
    print(f'Container {container_name} ({container_id}) is ready with root password: {ct_root_pw}')


def update_container(container_id):
    print(os_exec(f'echo "apk update && apk version" | pct console {container_id}', shell=True))
    print(os_exec(f'echo "apk upgrade" | pct console {container_id}', shell=True))


def get_ip(container_id, interface_id):
    # TODO: use generic "ip a" parse method from library here
    ip_output = os_exec(f'echo "ip a show eth{interface_id}" | pct console {container_id}', shell=True)
    ip4 = None
    ip6 = None
    for line in ip_output.split('\n'):
        if line.find('inet ') != -1:
            ip4 = line.split('inet ')[1].split(' ')[0].split('/')[0]
        elif line.find('inet6 ') != -1:
            ip6 = line.split('inet6 ')[1].split(' ')[0].split('/')[0]
    return ip4, ip6


def apk_add(container_id, package_name):
    os_exec(f'echo "apk add {package_name}" | pct console {container_id}', shell=True)
    # TODO: verify installation, also check if installed first?


def rc_update(container_id, service_name, operation):
    os_exec(f'echo "rc-update {operation} {service_name}" | pct console {container_id}', shell=True)
    # TODO: verify service change, check if it exists first?


def rc_service(container_id, service_name, operation):
    os_exec(f'echo "rc-service {service_name} {operation}" | pct console {container_id}', shell=True)
    # TODO: verify service status, check if it exists first?


def push_file(container_id, container_file_path, local_file_path):
    os_exec(f'pct push {container_id} {local_file_path} {container_file_path}')


def add_net(container_id, interface_id, vlan_tag=None, ip4=None, ip6=None):
    os_exec(f'pct set {container_id} {generate_net_argument(interface_id, vlan_tag, ip4, ip6)}')


def remove_net(container_id, interface_id):
    os_exec(f'pct set {container_id} --delete net{interface_id}')


def if_restart(container_id, interface_id):
    os_exec(f'echo "ifdown eth{interface_id}; ifup eth{interface_id}" | pct console {container_id}', shell=True)


def install_dhcpd(container_id, subnet):
    apk_add(container_id, 'dhcp-server-vanilla')
    rc_update(container_id, 'dhcpd', 'add')

    # /etc/dhcp - config
    # /var/lib/dhcp - leases/db
    # /run/dhcp - state/pid

    dhcpd_conf_temp_path = '/tmp/dhcpd.conf'
    dhcpd_conf = open('../templates/isc-dhcp-server/dhcpd.conf', 'r').read()
    open(dhcpd_conf_temp_path, 'w').write(dhcpd_conf)
    push_file(container_id, '/etc/dhcp/dhcpd.conf', dhcpd_conf_temp_path)

    dhcpd_conf_temp_path = '/tmp/dhcpd.subnets.conf'
    dhcpd_conf = open('../templates/isc-dhcp-server/dhcpd.subnets.conf', 'r').read()
    dhcpd_conf = dhcpd_conf.replace('1.2.3', subnet)
    open(dhcpd_conf_temp_path, 'w').write(dhcpd_conf)
    push_file(container_id, '/etc/dhcp/dhcpd.subnets.conf', dhcpd_conf_temp_path)

    dhcpd_conf_temp_path = '/tmp/dhcpd.devices.conf'
    dhcpd_conf = open('../templates/isc-dhcp-server/dhcpd.devices.conf', 'r').read()
    open(dhcpd_conf_temp_path, 'w').write(dhcpd_conf)
    push_file(container_id, '/etc/dhcp/dhcpd.devices.conf', dhcpd_conf_temp_path)

    rc_service(container_id, 'dhcpd', 'start')


class NetworkInterface:
    vlan_tag = None
    ip4 = None
    ip6 = None

    def __init__(self, vlan_tag=None, ip4=None, ip6=None):
        self.vlan_tag = vlan_tag
        self.ip4 = ip4
        self.ip6 = ip6


def main():
    alpine_newest_image_name = update_lxc_templates()
    # TODO: translate image names not just for local storage?
    image_path = f'/var/lib/vz/template/cache/{alpine_newest_image_name}'

    # Rework this into specific methods:
    # os_exec(f'echo "uname -a && ip a && uptime" | pct console {container_id}', shell=True)

    # Create DHCP server
    cid = 600
    purge_container(cid)
    create_container(cid, 'dhcp-test', image_path, [NetworkInterface(vlan_tag=5),
                                                    NetworkInterface(vlan_tag=100, ip4='10.100.0.1/24')])
    update_container(cid)
    print(get_ip(cid, 0))
    print(get_ip(cid, 1))
    install_dhcpd(cid, '10.100.0')

    # Create test client that uses the previously created DHCP server to acquire an IP
    cid = 601
    purge_container(cid)
    create_container(cid, 'ct-test', image_path, [NetworkInterface(vlan_tag=100)])
    # update_container(cid)
    time.sleep(1)
    print(get_ip(cid, 0))


if __name__ == '__main__':
    main()
