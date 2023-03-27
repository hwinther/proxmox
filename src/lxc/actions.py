import os

from src.common.common import os_exec, config


def update_lxc_templates():
    print('Updating pveam image list')
    os_exec('pveam update')

    alpine_newest = None
    for line in os_exec('pveam available --section system').split('\n'):
        if line.find('alpine-3') != -1:
            alpine_newest = line.replace('system', '').strip()
    if config.verbose:
        print(f'Newest alpine image: {alpine_newest}')

    alpine_newest_exists = os_exec(f'pveam list {config.template_storage}').find(alpine_newest) != -1
    if alpine_newest_exists:
        if config.verbose:
            print(f'Storage "{config.template_storage}" contains the image already.')
    else:
        print(f'Downloading newest alpine image to storage "{config.template_storage}"')
        os_exec(f'pveam download {config.template_storage} {alpine_newest}')

    return alpine_newest


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


def purge_container(container_id):
    # TODO: check pct list to see if id exists, then use configured option to determine if we're overwriting it or not
    os_exec(f'(pct stop {container_id}; pct destroy {container_id}); echo 0', shell=True)


def generate_net_argument(interface_id, vlan_tag=None, firewall=True, bridge=None,
                          ip4=None, gw4=None, ip6=None, gw6=None):
    vlan_arg = ''
    if vlan_tag is not None:
        vlan_arg = f'tag={vlan_tag},'

    firewall_arg = '1' if firewall else '0'

    bridge_arg = config.network_bridge_default if bridge is None else bridge

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

    return f'--net{interface_id} name=eth{interface_id},bridge={bridge_arg},' \
           f'ip={ip4}{gw4_arg},ip6={ip6}{gw6_arg},{vlan_arg}firewall={firewall_arg},type=veth'


def create_container(container_id, container_name, container_image_path, network_interfaces,
                     resource_pool=None, memory=None, swap=None, cpu_cores=None,
                     unprivileged=None, cmode=None, start=None, startup=None):
    if resource_pool is None:
        resource_pool = config.resource_pool_default
    if memory is None:
        memory = config.memory_default
    if swap is None:
        swap = config.swap_default
    if cpu_cores is None:
        cpu_cores = config.cpu_cores_default
    if unprivileged is None:
        unprivileged = 1
    if cmode is None:
        cmode = "shell"
    if start is None:
        start = 1
    if startup is None:
        startup = 0

    open(config.container_ssh_authorized_key_filename, 'w').write(config.container_ssh_authorized_key)

    network_arguments = []
    network_id = 0
    for network_interface in network_interfaces:
        network_arguments.append(generate_net_argument(network_id,
                                                       vlan_tag=network_interface.vlan_tag,
                                                       firewall=network_interface.firewall,
                                                       bridge=network_interface.bridge,
                                                       ip4=network_interface.ip4,
                                                       gw4=network_interface.gw4,
                                                       ip6=network_interface.ip6,
                                                       gw6=network_interface.gw6))
        network_id += 1

    cmd = f'pct create {container_id} {container_image_path} --ostype alpine --hostname {container_name}' \
          f' --password="ROOT_PASSWORD" --ssh-public-keys {config.container_ssh_authorized_key_filename}' \
          f' --cores {cpu_cores} --memory {memory} --swap {swap}' \
          f' --pool {resource_pool} --rootfs {config.container_storage}:0.1,shared=0' \
          f' --unprivileged {unprivileged} --cmode {cmode} --start {start} --startup {startup} ' \
          + ' '.join(network_arguments)

    # TODO: implement storage configuration:
    # f' --mp0 volume={container_storage}:0.01,mp=/etc/test,backup=1,ro=0,shared=0'

    env = os.environ.copy()
    ct_root_pw = config.container_root_password()
    env['ROOT_PASSWORD'] = ct_root_pw

    os_exec(cmd, env)
    # TODO: verify that it runs
    print(f'Container {container_name} ({container_id}) is ready with root password: {ct_root_pw}')
