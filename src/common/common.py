from __future__ import annotations

import configparser
import json
import hashlib
import secrets
import shlex
import string
import subprocess
import time
import os
import tempfile
from typing import Callable


class Config:
    verbose: bool | None = None
    template_storage: str | None = None
    container_storage: str | None = None
    container_root_password: Callable[[], str] | None = None
    container_ssh_authorized_key: str | None = None
    container_ssh_authorized_key_filename: str | None = None
    network_bridge_default: str | None = None
    resource_pool_default: str | None = None
    cpu_cores_default: int | None = None
    memory_default: int | None = None
    swap_default: int | None = None

    # muacme settings
    acme_email: str | None = None
    ddns_server: str | None = None
    ddns_tsig_key: str | None = None

    # remote node
    remote: bool | None = None
    remote_host: str | None = None

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
    lxc_node: 'LxcNode'

    # noinspection PyShadowingBuiltins
    def __init__(
        self,
        lxc_node,
        arch,
        cores,
        digest,
        hostname,
        memory,
        ostype,
        rootfs,
        swap,
        description=None,
        features=None,
        lxc=None,
        unprivileged=None,
        cmode=None,
        onboot=None,
        startup=None,
        parent=None,
        nameserver=None,
        mp0=None,
        mp1=None,
        mp2=None,
        mp3=None,
        mp4=None,
        mp5=None,
        mp6=None,
        mp7=None,
        mp8=None,
        mp9=None,
        net0=None,
        net1=None,
        net2=None,
        net3=None,
        net4=None,
        net5=None,
        net6=None,
        net7=None,
        net8=None,
        net9=None,
        dev0=None,
        searchdomain=None,
    ):
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
        self.nameserver = nameserver
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
        self.dev0 = dev0
        self.searchdomain = searchdomain

    def __str__(self):
        return f'{self.hostname} of type {self.ostype}'


class LxcNode:
    # noinspection PyShadowingBuiltins
    def __init__(
        self,
        pve_node,
        vmid,
        cpu,
        cpus,
        disk,
        diskread,
        diskwrite,
        maxdisk,
        maxmem,
        maxswap,
        mem,
        name,
        netin,
        netout,
        status,
        swap,
        type,
        uptime,
        pid=None,
        pressurecpufull=None,
        pressurecpusome=None,
        pressureiofull=None,
        pressureiosome=None,
        pressurememoryfull=None,
        pressurememorysome=None,
    ):
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
        return LxcConfig(
            lxc_node=self,
            **json.loads(
                os_exec_cached(
                    f'pvesh get nodes/{self.pve_node.node}/lxc/{self.vmid}/config --output-format=json',
                    cache_duration=3600,
                    local_override=True,
                )
            ),
        )


class PveNode:
    # noinspection PyShadowingBuiltins
    def __init__(
        self,
        id,
        node,
        ssl_fingerprint,
        status,
        type,
        cpu=None,
        disk=None,
        level=None,
        maxcpu=None,
        maxdisk=None,
        maxmem=None,
        mem=None,
        uptime=None,
    ):
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
        self.is_remote = False

    def __str__(self):
        return f'{self.node} of type {self.type} with status {self.status}'

    def get_lxc_nodes(self):
        return [
            LxcNode(pve_node=self, **node)
            for node in json.loads(
                os_exec(f'pvesh get nodes/{self.node}/lxc --output-format=json', local_override=True)
            )
        ]


config = Config()
_exec_cache = {}
_cache_file_path = os.path.join(tempfile.gettempdir(), 'proxmox_exec_cache.json')


def _get_cache_key(cmd, env=None, local_override=False, **kwargs):
    """Generate a unique cache key for the command and its parameters."""
    cache_data = {
        'cmd': cmd,
        'env': env,
        'local_override': local_override,
        'remote': config.remote,
        'remote_host': config.remote_host if config.remote else None,
        'kwargs': sorted(kwargs.items()),
    }
    return hashlib.md5(str(cache_data).encode()).hexdigest()


def _is_cache_valid(cache_entry, cache_duration):
    """Check if cache entry is still valid based on duration."""
    return time.time() - cache_entry['timestamp'] < cache_duration


def _load_cache():
    """Load cache from file if it exists."""
    global _exec_cache
    try:
        if os.path.exists(_cache_file_path):
            with open(_cache_file_path, 'r') as f:
                _exec_cache = json.load(f)
            if config.verbose:
                print(f'loaded cache from {_cache_file_path} with {len(_exec_cache)} entries')
        else:
            if config.verbose:
                print(f'Did not find cache data at expected location {_cache_file_path}')
    except (json.JSONDecodeError, IOError) as e:
        if config.verbose:
            print(f'failed to load cache: {e}')
        _exec_cache = {}


def _save_cache():
    """Save cache to file."""
    try:
        with open(_cache_file_path, 'w') as f:
            json.dump(_exec_cache, f)
        if config.verbose:
            print(f'saved cache to {_cache_file_path} with {len(_exec_cache)} entries')
    except IOError as e:
        if config.verbose:
            print(f'failed to save cache: {e}')


def generate_random_password(length: int):
    alphabet = string.ascii_letters + string.digits  # + string.punctuation
    password = ''
    for i in range(length):
        password += ''.join(secrets.choice(alphabet))
    return password


def os_exec_cached(cmd, cache_duration: int = 300, env=None, local_override: bool = False, **kwargs):
    # Load cache on first use
    if not _exec_cache:
        _load_cache()

    cache_key = _get_cache_key(cmd, env, local_override, **kwargs)
    if cache_key in _exec_cache:
        cache_entry = _exec_cache[cache_key]
        if _is_cache_valid(cache_entry, cache_duration):
            if config.verbose:
                print(f'using cached result for: {cmd}')
            return cache_entry['output']
        else:
            del _exec_cache[cache_key]

    output = os_exec(cmd, env, local_override, **kwargs)
    _exec_cache[cache_key] = {'output': output, 'timestamp': time.time()}
    _save_cache()
    return output


class PveCommandError(RuntimeError):
    def __init__(self, cmd, returncode: int, stdout: str, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(
            f'command exited with status {returncode}: {cmd!r}\n' f'stdout: {stdout.strip()}\nstderr: {stderr.strip()}'
        )


def os_exec(cmd, env=None, local_override: bool = False, remote_host: str = None, **kwargs):
    if config.verbose:
        print(f'executing: {cmd}')
    if (config.remote or remote_host is not None) and not local_override:
        if remote_host is None:
            remote_host = config.remote_host
        cmd_str = cmd if isinstance(cmd, str) else shlex.join(cmd)
        cmds = shlex.split(f'ssh {remote_host} {shlex.quote(cmd_str)}')
        if 'shell' in kwargs:
            kwargs['shell'] = False
            if config.verbose:
                print('disabled shell flag due to executing the command via a remote host')
        if config.verbose:
            print(f'updated cmd: {cmds}')
    elif isinstance(cmd, list):
        cmds = cmd
    elif 'shell' in kwargs:
        cmds = cmd
    else:
        cmds = shlex.split(cmd)
    process = subprocess.run(cmds, capture_output=True, env=env, **kwargs)
    stderr = process.stderr.decode('utf-8')
    stdout = process.stdout.decode('utf-8')
    if stderr != '':
        print(f'stderr: {stderr}')
    if process.returncode != 0:
        raise PveCommandError(cmd=cmd, returncode=process.returncode, stdout=stdout, stderr=stderr)
    if config.verbose and stdout != '':
        print(f'stdout: {stdout}')
    return stdout


def pvesh_get_pve_nodes():
    return [
        PveNode(**node)
        for node in json.loads(os_exec_cached('pvesh get nodes --output-format=json', local_override=True))
    ]
