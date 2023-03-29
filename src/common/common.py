import configparser
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
        self.container_ssh_authorized_key = default.get('container_ssh_authorized_key')  # default: ed25519-key-20171113
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


config = Config()


def generate_random_password(length: int):
    alphabet = string.ascii_letters + string.digits  # + string.punctuation
    password = ''
    for i in range(length):
        password += ''.join(secrets.choice(alphabet))
    return password


def os_exec(cmd, env=None, **kwargs):
    if config.verbose:
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
    if config.verbose and stdout != '':
        print(f'stdout: {stdout}')
    return stdout
