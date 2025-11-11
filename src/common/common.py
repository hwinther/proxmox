import configparser
import json
import secrets
import string
import subprocess
from typing import Callable


class Config:
    verbose: bool = None
    template_storage: str = None
    container_storage: str = None
    container_root_password: Callable[[], str] = None
    container_ssh_authorized_key: str = None
    container_ssh_authorized_key_filename: str = None
    network_bridge_default: str = None
    resource_pool_default: str = None
    cpu_cores_default: int = None
    memory_default: int = None
    swap_default: int = None

    # muacme settings
    acme_email: str = None
    ddns_server: str = None
    ddns_tsig_key: str = None

    # remote node
    remote: bool = None
    remote_host: str = None

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        default = self.config[self.config.default_section]
        self.verbose = default.getboolean('verbose')  # default: False
        if self.verbose is None:
            self.verbose = False

        # PVE storage, local, local_zfs
        self.template_storage = default.get('template_storage')  # default: local
        if self.template_storage is None:
            raise ValueError('template_storage was not configured')
        self.container_storage = default.get('container_storage')  # default: local_zfs
        if self.container_storage is None:
            raise ValueError('container_storage was not configured')

        # container_root_password = lambda: 'static_and_less_safe_password'
        self.container_root_password = lambda: generate_random_password(32)

        # noinspection SpellCheckingInspection
        self.container_ssh_authorized_key = default.get('container_ssh_authorized_key')  # default: ed25519-key
        if self.container_ssh_authorized_key is None:
            raise ValueError('container_ssh_authorized_key was not configured')
        self.container_ssh_authorized_key_filename = '/tmp/container_ssh_authorized_key'

        self.network_bridge_default = default.get('network_bridge_default')  # default: vmbr0
        if self.network_bridge_default is None:
            raise ValueError('network_bridge_default was not configured')

        self.resource_pool_default = default.get('resource_pool_default')  # default: Testing
        if self.resource_pool_default is None:
            raise ValueError('resource_pool_default was not configured')

        self.cpu_cores_default = default.getint('cpu_cores_default')  # default: 2
        if self.cpu_cores_default is None:
            raise ValueError('cpu_cores_default was not configured')

        self.memory_default = default.getint('memory_default')  # default: 128
        if self.memory_default is None:
            raise ValueError('memory_default was not configured')

        self.swap_default = default.getint('swap_default')  # default: 128
        if self.swap_default is None:
            raise ValueError('swap_default was not configured')

        # muacme settings TODO: move muacme settings to separate section and disable functionality if missing
        self.acme_email = default.get('acme_email')
        if self.acme_email is None:
            raise ValueError('acme_email was not configured')
        self.ddns_server = default.get('ddns_server')
        if self.ddns_server is None:
            raise ValueError('ddns_server was not configured')
        self.ddns_tsig_key = default.get('ddns_tsig_key')
        if self.ddns_tsig_key is None:
            raise ValueError('ddns_tsig_key was not configured')

        # remote node
        self.remote = default.getboolean('remote')
        if self.remote is None:
            raise ValueError('remote was not configured')
        self.remote_host = default.get('remote_host')
        if self.remote_host is None:
            raise ValueError('remote_host was not configured')


class LxcConfig:
    lxc_node: 'LxcNode' = None
    arch = None
    cmode = None
    cores = None
    description = None
    digest = None
    features = None
    hostname = None
    lxc = None
    memory = None
    mp0 = None
    mp1 = None
    mp2 = None
    mp3 = None
    mp4 = None
    mp5 = None
    mp6 = None
    mp7 = None
    mp8 = None
    mp9 = None
    net0 = None
    net1 = None
    net2 = None
    net3 = None
    net4 = None
    net5 = None
    net6 = None
    net7 = None
    net8 = None
    net9 = None
    onboot = None
    ostype = None
    rootfs = None
    swap = None
    unprivileged = None
    startup = None
    parent = None

    # noinspection PyShadowingBuiltins
    def __init__(self, lxc_node, arch, cores, digest, hostname, memory, ostype, rootfs, swap,
                 description=None, features=None, lxc=None, unprivileged=None,
                 cmode=None, onboot=None, startup=None, parent=None,
                 mp0=None, mp1=None, mp2=None, mp3=None, mp4=None, mp5=None,
                 mp6=None, mp7=None, mp8=None, mp9=None,
                 net0=None, net1=None, net2=None, net3=None, net4=None,
                 net5=None, net6=None, net7=None, net8=None, net9=None):
        self.lxc_node = lxc_node
        self.arch = arch
        self.cmode = cmode
        self.cores = cores
        self.description = description
        self.digest = digest
        self.features = features
        self.hostname = hostname
        self.lxc = lxc
        self.memory = memory
        self.onboot = onboot
        self.ostype = ostype
        self.rootfs = rootfs
        self.startup = startup
        self.parent = parent
        self.swap = swap
        self.unprivileged = unprivileged
        self.mp0 = mp0
        self.mp1 = mp1
        self.mp2 = mp2
        self.mp3 = mp3
        self.mp4 = mp4
        self.mp5 = mp5
        self.mp6 = mp6
        self.mp7 = mp7
        self.mp8 = mp8
        self.mp9 = mp9
        self.net0 = net0
        self.net1 = net1
        self.net2 = net2
        self.net3 = net3
        self.net4 = net4
        self.net5 = net5
        self.net6 = net6
        self.net7 = net7
        self.net8 = net8
        self.net9 = net9

    def __str__(self):
        return f'{self.hostname} of type {self.ostype}'


class LxcNode:
    pve_node = None
    vmid = None
    cpu = None
    cpus = None
    disk = None
    diskread = None
    diskwrite = None
    maxdisk = None
    maxmem = None
    maxswap = None
    mem = None
    name = None
    netin = None
    netout = None
    pid = None
    status = None
    swap = None
    type = None
    uptime = None
    pressurecpufull = None
    pressurecpusome = None
    pressureiofull = None
    pressureiosome = None
    pressurememoryfull = None
    pressurememorysome = None

    # noinspection PyShadowingBuiltins
    def __init__(self, pve_node, vmid, cpu, cpus, disk, diskread, diskwrite, maxdisk, maxmem, maxswap, mem, name,
                 netin, netout, status, swap, type, uptime, pid=None, pressurecpufull=None, pressurecpusome=None,
                 pressureiofull=None, pressureiosome=None, pressurememoryfull=None, pressurememorysome=None):
        self.pve_node = pve_node
        self.vmid = vmid
        self.cpu = cpu
        self.cpus = cpus
        self.disk = disk
        self.diskread = diskread
        self.diskwrite = diskwrite
        self.maxdisk = maxdisk
        self.maxmem = maxmem
        self.maxswap = maxswap
        self.mem = mem
        self.name = name
        self.netin = netin
        self.netout = netout
        self.pid = pid
        self.status = status
        self.swap = swap
        self.type = type
        self.uptime = uptime
        self.pressurecpufull = pressurecpufull
        self.pressurecpusome = pressurecpusome
        self.pressureiofull = pressureiofull
        self.pressureiosome = pressureiosome
        self.pressurememoryfull = pressurememoryfull
        self.pressurememorysome = pressurememorysome

    def __str__(self):
        return f'{self.vmid} of type {self.type} with status {self.status}'

    def get_lxc_config(self):
        return LxcConfig(lxc_node=self, **json.loads(
            os_exec(f'pvesh get nodes/{self.pve_node.node}/lxc/{self.vmid}/config --output-format=json',
                    local_override=True)))


class PveNode:
    id = None
    cpu = None
    disk = None
    level = None
    maxcpu = None
    maxdisk = None
    maxmem = None
    mem = None
    node = None
    ssl_fingerprint = None
    status = None
    type = None
    uptime = None

    # noinspection PyShadowingBuiltins
    def __init__(self, id, node, ssl_fingerprint, status, type, cpu=None, disk=None, level=None, maxcpu=None,
                 maxdisk=None, maxmem=None, mem=None, uptime=None):
        self.id = id
        self.cpu = cpu
        self.disk = disk
        self.level = level
        self.maxcpu = maxcpu
        self.maxdisk = maxdisk
        self.maxmem = maxmem
        self.mem = mem
        self.node = node
        self.ssl_fingerprint = ssl_fingerprint
        self.status = status
        self.type = type
        self.uptime = uptime

    def __str__(self):
        return f'{self.node} of type {self.type} with status {self.status}'

    def get_lxc_nodes(self):
        return [LxcNode(pve_node=self, **node) for node in
                json.loads(os_exec(f'pvesh get nodes/{self.node}/lxc --output-format=json', local_override=True))]


config = Config()


def generate_random_password(length: int):
    alphabet = string.ascii_letters + string.digits  # + string.punctuation
    password = ''
    for i in range(length):
        password += ''.join(secrets.choice(alphabet))
    return password


def os_exec(cmd, env=None, local_override: bool = False, **kwargs):
    if config.verbose:
        print(f'executing: {cmd}')
    if config.remote and not local_override:
        import shlex
        cmds = shlex.split(f'ssh {config.remote_host} {shlex.quote(cmd)}')
        if 'shell' in kwargs:
            kwargs['shell'] = False
            if config.verbose:
                print('disabled shell flag')
        if config.verbose:
            print(f'updated cmd: {cmds}')
    elif 'shell' in kwargs:
        cmds = cmd
    else:
        cmds = cmd.split(' ')
    process = subprocess.run(cmds, capture_output=True, env=env, **kwargs)
    stderr = process.stderr.decode('utf-8')
    if stderr != '':
        print(f'stderr: {stderr}')
    process.check_returncode()
    stdout = process.stdout.decode('utf-8')
    if config.verbose and stdout != '':
        print(f'stdout: {stdout}')
    return stdout


def pvesh_get_pve_nodes():
    return [PveNode(**node) for node in
            json.loads(os_exec('pvesh get nodes --output-format=json', local_override=True))]
