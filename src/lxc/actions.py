import os
from typing import Sequence

from src.common.common import config, os_exec
from src.lxc.models import NetworkInterface


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


def generate_net_argument(interface_id: int, network_interface: NetworkInterface = None,
                          vlan_tag: int = None, firewall: bool = True, bridge: str = None,
                          ip4: str = None, gw4: str = None, ip6: str = None, gw6: str = None):
    if network_interface is not None:
        vlan_tag = network_interface.vlan_tag
        firewall = network_interface.firewall
        bridge = network_interface.bridge
        if network_interface.ip4 is not None:
            ip4 = str(network_interface.ip4)
        if network_interface.gw4 is not None:
            gw4 = str(network_interface.gw4)
        if network_interface.ip6 is not None:
            ip6 = str(network_interface.ip6)
        if network_interface.gw6 is not None:
            gw6 = str(network_interface.gw6)

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


class Container:
    id: int = None

    def __init__(self, container_id: int):
        self.id = container_id

    def push_file(self, container_file_path: str, local_file_path: str):
        return os_exec(f'pct push {self.id} {local_file_path} {container_file_path}')

    def add_net(self, interface_id: int, vlan_tag: int = None, ip4: str = None, ip6: str = None):
        return os_exec(f'pct set {self.id} {generate_net_argument(interface_id, vlan_tag=vlan_tag, ip4=ip4, ip6=ip6)}')

    def remove_net(self, interface_id: int):
        return os_exec(f'pct set {self.id} --delete net{interface_id}')

    def if_restart(self, interface_id: int):
        return self.pct_console_shell(f"ifdown eth{interface_id}; ifup eth{interface_id}")

    def pct_console_shell(self, container_command: str):
        return os_exec(f'echo "{container_command}" | pct console {self.id}', shell=True)

    def purge_container(self):
        # TODO: check pct list to see if id exists, then use configured option to determine
        #  if we're overwriting it or not
        os_exec(f'(pct stop {self.id}; pct destroy {self.id}); echo 0', shell=True)

    def create_container(self, container_name: str, container_image_path: str,
                         network_interfaces: Sequence[NetworkInterface],
                         resource_pool=None, memory=None, swap=None, cpu_cores=None,
                         unprivileged=None, cmode=None, start=None, startup=None):
        #
        # TODO: rework this to a factory constructor with override in AlpineContainer?
        #
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
            network_arguments.append(generate_net_argument(network_id, network_interface=network_interface))
            network_id += 1

        cmd = f'pct create {self.id} {container_image_path} --ostype alpine --hostname {container_name}' \
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
        print(f'Container {container_name} ({self.id}) is ready with root password: {ct_root_pw}')
    