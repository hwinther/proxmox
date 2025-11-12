import os
import platform
import tempfile
from typing import List, Sequence

from common.common import LxcConfig, PveNode, config, os_exec, pvesh_get_pve_nodes
from lxc.models import NetworkInterface


def update_lxc_templates():
    print('Updating pveam image list')
    os_exec('pveam update')

    alpine_newest = None
    debian_newest = None
    for line in os_exec('pveam available --section system').split('\n'):
        if line.find('alpine-') != -1:
            alpine_newest = line.replace('system', '').strip()
        elif line.find('debian-') != -1:
            debian_newest = line.replace('system', '').strip()
    if config.verbose:
        print(f'Newest alpine image: {alpine_newest}')
        print(f'Newest debian image: {debian_newest}')

    alpine_newest_exists = os_exec(f'pveam list {config.template_storage}').find(alpine_newest) != -1
    if alpine_newest_exists:
        if config.verbose:
            print(f'Storage "{config.template_storage}" contains the alpine image already.')
    else:
        print(f'Downloading newest alpine image to storage "{config.template_storage}"')
        os_exec(f'pveam download {config.template_storage} {alpine_newest}')

    debian_newest_exists = os_exec(f'pveam list {config.template_storage}').find(debian_newest) != -1
    if debian_newest_exists:
        if config.verbose:
            print(f'Storage "{config.template_storage}" contains the debian image already.')
    else:
        print(f'Downloading newest debian image to storage "{config.template_storage}"')
        os_exec(f'pveam download {config.template_storage} {debian_newest}')

    return alpine_newest, debian_newest


def generate_net_argument(interface_id: int, network_interface: NetworkInterface = None,
                          vlan_tag: int = None, firewall: bool = True, bridge: str = None, mac: str = None,
                          ip4: str = None, gw4: str = None, ip6: str = None, gw6: str = None):
    if network_interface is not None:
        vlan_tag = network_interface.vlan_tag
        firewall = network_interface.firewall
        bridge = network_interface.bridge
        mac = network_interface.mac
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

    mac_arg = '' if mac is None else f'hwaddr={mac},'

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

    return f'--net{interface_id} name=eth{interface_id},bridge={bridge_arg},{mac_arg}' \
           f'ip={ip4}{gw4_arg},ip6={ip6}{gw6_arg},{vlan_arg}firewall={firewall_arg},type=veth'


class Service:
    container: "Container" = None
    name: str = None

    def __init__(self, container: "Container", name: str):
        self.container = container
        self.name = name

    def install(self, **kwargs):
        raise NotImplementedError('install was not implemented')

    def uninstall(self, **kwargs):
        raise NotImplementedError('uninstall was not implemented')

    def start(self, **kwargs):
        raise NotImplementedError('start was not implemented')

    def stop(self, **kwargs):
        raise NotImplementedError('stop was not implemented')


class Container:
    id: int = None
    network_interfaces: List[NetworkInterface] = None
    services: List[Service] = None
    lxc_config: LxcConfig = None
    pve_node: PveNode = None

    def __init__(self, container_id: int = None, lxc_config: LxcConfig = None, pve_node: PveNode = None):
        if container_id is not None:
            self.id = container_id
        elif lxc_config is not None:
            self.id = lxc_config.lxc_node.vmid
            self.lxc_config = lxc_config
        else:
            raise ValueError("container_id or lxc_config must be specified")

        self.network_interfaces = []
        self.services = []
        self.pve_node = pve_node

    def push_file(self, container_file_path: str, local_file_path: str):
        # TODO: file write/read is not properly redirected yet
        if self.pve_node is not None and self.pve_node.is_remote:
            print('will not work')
            # TODO: try scp {local_file_path} {remote_host}/{local_file_path}
        return os_exec(f'pct push {self.id} {local_file_path} {container_file_path}')

    def push_file_from_template(self, container_file_path: str, template_file_path: str, **kwargs):
        with tempfile.NamedTemporaryFile() as temporary_file:
            template = open(template_file_path, 'r', encoding='utf-8').read()
            for key, value in kwargs.items():
                if config.verbose:
                    print(f'replacing "{key}" with "{value}" in template data from {template_file_path}')
                template = template.replace(key, value)
            temporary_file.write(template.encode('utf-8'))
            temporary_file.flush()
            return_value = self.push_file(container_file_path, temporary_file.name)
            return return_value

    def add_net(self, interface_id: int, vlan_tag: int = None, ip4: str = None, ip6: str = None):
        return os_exec(f'pct set {self.id} {generate_net_argument(interface_id, vlan_tag=vlan_tag, ip4=ip4, ip6=ip6)}', remote_host=self.get_remote_host_value())

    def remove_net(self, interface_id: int):
        return os_exec(f'pct set {self.id} --delete net{interface_id}', remote_host=self.get_remote_host_value())

    def if_restart(self, interface_id: int):
        return self.pct_console_shell(f'ifdown eth{interface_id}; ifup eth{interface_id}')

    def append_file(self, file_path, text_line):
        return self.pct_console_shell(f"echo '{text_line}' >> {file_path}")

    def pct_console_shell(self, container_command: str):
        return os_exec(f'echo "{container_command}" | pct console {self.id}', shell=True, remote_host=self.get_remote_host_value())

    def pct_get_os_version(self):
        raise NotImplementedError("pct_get_os_version was not implemented")

    def get_remote_host_value(self):
        return self.pve_node.node if self.pve_node is not None and self.pve_node.is_remote else None

    @staticmethod
    def pct_list():
        # Rather than parsing pct list and pct config output, we can use pvesh and get more details
        # pct_list = os_exec('pct list').split('\n')
        active_configs = {}
        pve_nodes = pvesh_get_pve_nodes()
        for pve_node in pve_nodes:
            if pve_node.status != 'online':
                continue

            if config.remote:
                if pve_node.node != config.remote_host:
                    if config.verbose:
                        print(f"found non-remote node {pve_node.node}")
                    pve_node.is_remote = True
            elif pve_node.node != platform.node():
                if config.verbose:
                    print(f"found non-local node {pve_node.node}")
                pve_node.is_remote = True

            # print(str(pve_node))

            lxc_nodes = pve_node.get_lxc_nodes()
            for lxc_node in lxc_nodes:
                if lxc_node.status != 'running':
                    continue

                # print(str(lxc_node))

                lxc_config = lxc_node.get_lxc_config()
                # print(str(lxc_config))

                if pve_node not in active_configs.keys():
                    active_configs[pve_node] = []

                active_configs[pve_node].append(lxc_config)

        return active_configs

    @staticmethod
    def purge_container_by_id(container_id: int):
        # TODO: check pct list to see if id exists, then use configured option to determine
        #  if we're overwriting it or not
        # os_exec(f'(pct shutdown {container_id}; pct stop {container_id}; pct destroy {container_id}); echo 0',
        os_exec(f'(pct shutdown {container_id}; pct destroy {container_id}); echo 0',
                shell=True)

    def purge_container(self):
        self.purge_container_by_id(self.id)

    def create_container(self, container_name: str, container_image_path: str,
                         network_interfaces: Sequence[NetworkInterface],
                         resource_pool: str = None, memory: int = None, swap: int = None, cpu_cores: int = None,
                         unprivileged: int = None, cmode: str = None, start: int = None, onboot: int = None,
                         feature_mount: str = None, feature_nesting: int = None, rootfs_size: str = None):
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
        if onboot is None:
            onboot = 0

        open(config.container_ssh_authorized_key_filename, 'w').write(config.container_ssh_authorized_key)

        network_arguments = []
        network_id = 0
        for network_interface in network_interfaces:
            network_arguments.append(generate_net_argument(network_id, network_interface=network_interface))
            self.network_interfaces.append(network_interface)
            network_id += 1

        features = []
        if feature_mount is not None:
            features.append(f'mount={feature_mount}')
        if feature_nesting is not None:
            features.append(f'nesting={feature_nesting}')
        feature_set = ''
        if len(features) != 0:
            feature_set = ' --features ' + ','.join(features)

        if rootfs_size is None:
            rootfs_size = '0.1'  # 100MB

        cmd = f'pct create {self.id} {container_image_path} --ostype alpine --hostname {container_name}' \
              f' --password="ROOT_PASSWORD" --ssh-public-keys {config.container_ssh_authorized_key_filename}' \
              f' --cores {cpu_cores} --memory {memory} --swap {swap}' \
              f' --pool {resource_pool} --rootfs {config.container_storage}:{rootfs_size},shared=0' \
              f' --unprivileged {unprivileged} --cmode {cmode} --start {start} --onboot {onboot}' \
              f'{feature_set}' \
              + ' ' + ' '.join(network_arguments)

        # TODO: implement storage configuration:
        # f' --mp0 volume={container_storage}:0.01,mp=/etc/test,backup=1,ro=0,shared=0'

        env = os.environ.copy()
        ct_root_pw = config.container_root_password()
        env['ROOT_PASSWORD'] = ct_root_pw

        os_exec(cmd, env)
        # TODO: verify that it runs
        print(f'Container {container_name} ({self.id}) is ready with root password: {ct_root_pw}')
