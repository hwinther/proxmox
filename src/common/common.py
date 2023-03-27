import configparser
import secrets
import string
import subprocess


class Config:
    verbose = None

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('default.ini')

        self.verbose = self.config[self.config.default_section].getboolean('Verbose')

        # PVE storage, local, local_zfs
        self.template_storage = 'local'
        self.container_storage = 'local_zfs'

        # container_root_password = lambda: 'static_and_less_safe_password'
        self.container_root_password = lambda: generate_random_password(32)

        # noinspection SpellCheckingInspection
        self.container_ssh_authorized_key = 'ssh-ed25519 ' \
                                            'AAAAC3NzaC1lZDI1NTE5AAAAIGzYkv5+lko9E5Tpc3wHg1ZDm4DZDo/ahtljV3xfiHhf ' \
                                            'ed25519-key-20171113'
        self.container_ssh_authorized_key_filename = '/tmp/container_ssh_authorized_key'
        self.network_bridge_default = 'vmbr0'
        self.resource_pool_default = 'Testing'
        self.cpu_cores_default = 2
        self.memory_default = 128
        self.swap_default = 128


config = Config()


def generate_random_password(length):
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
