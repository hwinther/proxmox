import os
import subprocess
import secrets
import string


def generate_random_password(length):
    alphabet = string.ascii_letters + string.digits  # + string.punctuation
    password = ''
    for i in range(length):
        password += ''.join(secrets.choice(alphabet))
    return password


# TODO: move config to separate file and only have sample in repo
# PVE storage, local, local_zfs
template_storage = 'local'
container_storage = 'local_zfs'
# container_root_password = lambda: 'static_and_less_safe_password'
container_root_password = lambda: generate_random_password(32)
# noinspection SpellCheckingInspection
container_ssh_authorized_key = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGzYkv5+lko9E5Tpc3wHg1ZDm4DZDo/ahtljV3xfiHhf' \
                               ' ed25519-key-20171113'
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

    alpine_newest_exists = os_exec(f'pveam list {template_storage}').find(alpine_newest) != -1
    if alpine_newest_exists:
        if verbose:
            print(f'Storage "{template_storage}" contains the image already.')
    else:
        print(f'Downloading newest alpine image to storage "{template_storage}"')
        os_exec(f'pveam download {template_storage} {alpine_newest}')

    return alpine_newest


def purge_container(container_id):
    # TODO: check pct list to see if id exists, then use configured option to determine if we're overwriting it or not
    os_exec(f'(pct stop {container_id}; pct destroy {container_id}); echo 0', shell=True)


def generate_net_argument(interface_id, vlan_tag=None, ip4=None, gw4=None, ip6=None, gw6=None, firewall=True):
    vlan_arg = ''
    if vlan_tag is not None:
        vlan_arg = f'tag={vlan_tag},'

    if ip4 is None:
        ip4 = 'dhcp'
    gw4_arg = ''
    if gw4 is not None:
        gw4_arg = f',gw={gw4}'

    if ip6 is None:
        ip6 = 'auto'
    gw6_arg = ''
    if gw6 is not None:
        gw6_arg = f',gw={gw6}'

    firewall_arg = '1' if firewall else '0'

    return f'--net{interface_id} name=eth{interface_id},bridge={network_bridge},' \
           f'ip={ip4}{gw4_arg},ip6={ip6}{gw6_arg},{vlan_arg}firewall={firewall_arg},type=veth'


def create_container(container_id, container_name, container_image_path, network_interfaces):
    open(container_ssh_authorized_key_filename, 'w').write(container_ssh_authorized_key)

    network_arguments = []
    network_id = 0
    for network_interface in network_interfaces:
        network_arguments.append(generate_net_argument(network_id,
                                                       network_interface.vlan_tag,
                                                       network_interface.ip4,
                                                       network_interface.gw4,
                                                       network_interface.ip6,
                                                       network_interface.gw6,
                                                       network_interface.firewall))
        network_id += 1

    cmd = f'pct create {container_id} {container_image_path} --hostname {container_name}' \
          f' --memory {memory} --swap {swap}' \
          f' --rootfs {container_storage}:0.1,shared=0' \
          f' --unprivileged 1 --pool {resource_pool} --ssh-public-keys {container_ssh_authorized_key_filename}' \
          f' --ostype alpine --password="ROOT_PASSWORD" --cmode shell --cores {cpu_cores} --start 1 ' \
          + ' '.join(network_arguments)

    # TODO: implement storage configuration:
    # f' --mp0 volume={container_storage}:0.01,mp=/etc/test,backup=1,ro=0,shared=0'

    env = os.environ.copy()
    ct_root_pw = container_root_password()
    env['ROOT_PASSWORD'] = ct_root_pw

    os_exec(cmd, env)
    # TODO: verify that it runs
    print(f'Container {container_name} ({container_id}) is ready with root password: {ct_root_pw}')


def update_container(container_id):
    print(pct_console_shell(container_id, f"apk update && apk version"))
    print(pct_console_shell(container_id, f"apk upgrade"))


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
    return pct_console_shell(container_id, f"apk add {package_name}")
    # TODO: verify installation, also check if installed first?


def rc_update(container_id, service_name, operation):
    return pct_console_shell(container_id, f"rc-update {operation} {service_name}")
    # TODO: verify service change, check if it exists first?


def rc_service(container_id, service_name, operation):
    return pct_console_shell(container_id, f"rc-service {service_name} {operation}")
    # TODO: verify service status, check if it exists first?


def push_file(container_id, container_file_path, local_file_path):
    return os_exec(f'pct push {container_id} {local_file_path} {container_file_path}')


def add_net(container_id, interface_id, vlan_tag=None, ip4=None, ip6=None):
    return os_exec(f'pct set {container_id} {generate_net_argument(interface_id, vlan_tag, ip4, ip6)}')


def remove_net(container_id, interface_id):
    return os_exec(f'pct set {container_id} --delete net{interface_id}')


def if_restart(container_id, interface_id):
    return pct_console_shell(container_id, f"ifdown eth{interface_id}; ifup eth{interface_id}")


def pct_console_shell(container_id, container_command):
    return os_exec(f'echo "{container_command}" | pct console {container_id}', shell=True)


def install_isc_dhcpd(container_id, subnet):
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


def install_gateway_nat(container_id):
    apk_add(container_id, 'ip6tables')
    apk_add(container_id, 'awall')

    rc_update(container_id, 'iptables', 'add')
    rc_update(container_id, 'ip6tables', 'add')

    # /etc/awall/optional/ - inactive config folder

    awall_policy_temp_path = '/tmp/gateway-nat-policy.json'
    dhcpd_conf = open('../templates/awall/gateway-nat-policy.json', 'r').read()
    open(awall_policy_temp_path, 'w').write(dhcpd_conf)
    push_file(container_id, '/etc/awall/optional/gateway-nat-policy.json', awall_policy_temp_path)

    # Enable and activate firewall rules
    pct_console_shell(container_id, "awall enable gateway-nat-policy && awall activate -f")

    # Enable routing via sysctl, in the future perhaps also enable ipv6 forwarding?
    pct_console_shell(container_id, "sysctl -w net.ipv4.ip_forward=1")

    rc_service(container_id, 'iptables', 'start')
    rc_service(container_id, 'ip6tables', 'start')


def install_bind_dns(container_id, subnet):
    apk_add(container_id, 'bind')
    rc_update(container_id, 'named', 'add')

    # /etc/bind - config
    # /var/bind - zones/db
    #   sub directories dyn|pri|sec for specific zone types
    # /run/named - state/pid

    named_conf_temp_path = '/tmp/named.conf'
    named_conf = open('../templates/bind9/named.conf.recursive', 'r').read()
    named_conf = named_conf.replace('1.2.3', subnet)
    open(named_conf_temp_path, 'w').write(named_conf)
    push_file(container_id, '/etc/bind/named.conf', named_conf_temp_path)

    rc_service(container_id, 'named', 'start')


class NetworkInterface:
    vlan_tag = None
    ip4 = None
    gw4 = None
    ip6 = None
    gw6 = None
    firewall = True

    def __init__(self, vlan_tag=None, ip4=None, gw4=None, ip6=None, gw6=None, firewall=True):
        self.vlan_tag = vlan_tag
        self.ip4 = ip4
        self.gw4 = gw4
        self.ip6 = ip6
        self.gw6 = gw6
        self.firewall = firewall


def main():
    alpine_newest_image_name = update_lxc_templates()
    # TODO: translate image names not just for local (template_)storage?
    image_path = f'/var/lib/vz/template/cache/{alpine_newest_image_name}'

    # Create NAT gateway
    cid = 601
    purge_container(cid)
    create_container(cid, 'gateway-test', image_path, [NetworkInterface(),
                                                       NetworkInterface(vlan_tag=100, ip4='10.100.0.1/24')])
    update_container(cid)
    print(get_ip(cid, 0))
    print(get_ip(cid, 1))
    install_gateway_nat(cid)

    # Create DNS server
    cid = 602
    purge_container(cid)
    create_container(cid, 'dns-test', image_path, [NetworkInterface(vlan_tag=100,
                                                                    ip4='10.100.0.2/24',
                                                                    gw4='10.100.0.1')])
    update_container(cid)
    print(get_ip(cid, 0))
    install_bind_dns(cid, '10.100.0')

    # Create DHCP server
    cid = 603
    purge_container(cid)
    create_container(cid, 'dhcp-test', image_path, [NetworkInterface(vlan_tag=100,
                                                                     ip4='10.100.0.3/24',
                                                                     gw4='10.100.0.1')])
    update_container(cid)
    print(get_ip(cid, 0))
    install_isc_dhcpd(cid, '10.100.0')

    # Create test client that uses the previously created DHCP server to acquire an IP
    cid = 604
    purge_container(cid)
    create_container(cid, 'client-test', image_path, [NetworkInterface(vlan_tag=100)])
    update_container(cid)
    # time.sleep(1)
    print(get_ip(cid, 0))
    print(pct_console_shell(cid, 'uname -a'))


if __name__ == '__main__':
    main()
