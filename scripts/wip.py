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


def os_exec(cmd, env=None, **kwargs):
    print(f'executing: {cmd}')
    if 'shell' in kwargs:
        cmds = cmd
    else:
        cmds = cmd.split(' ')
    process = subprocess.run(cmds, capture_output=True, env=env, **kwargs)
    print('stderr: ' + process.stderr.decode('utf-8'))
    process.check_returncode()
    return process.stdout.decode('utf-8')


def update_lxc_templates():
    os_exec('pveam update')

    alpine_newest = None
    for line in os_exec('pveam available --section system').split('\n'):
        if line.find('alpine-3') != -1:
            alpine_newest = line.replace('system', '').strip()
    print(f'Newest alpine image: {alpine_newest}')

    alpine_newest_exists = os_exec(f'pveam list {storage}').find(alpine_newest) != -1
    if alpine_newest_exists:
        print(f'Storage "{storage}" contains the image already.')
    else:
        print(f'Downloading newest alpine image to storage "{storage}"')
        print(os_exec(f'pveam download {storage} {alpine_newest}'))

    return alpine_newest


def create_container(container_id, container_name, container_image_path):
    open(container_ssh_authorized_key_filename, 'w').write(container_ssh_authorized_key)

    # TODO: check pct list to see if id exists, then use configured option to determine if we're overwriting it or not
    os_exec(f'(pct stop {container_id}; pct destroy {container_id}); echo 0', shell=True)

    cmd = f'pct create {container_id} {container_image_path} --hostname {container_name}' \
          f' --memory {memory} --swap {swap}' \
          f' --net0 name=eth0,bridge={network_bridge},firewall=1,ip=dhcp,type=veth' \
          f' --storage {storage} --rootfs local:0.1' \
          f' --unprivileged 1 --pool {resource_pool} --ssh-public-keys {container_ssh_authorized_key_filename}' \
          f' --ostype alpine --password="ROOT_PASSWORD" --cmode shell --cores {cpu_cores} --start 1' \
          f' --mp0 volume={storage}:0.01,mp=/etc/testconfig,backup=1,ro=0,shared=0'
    env = os.environ.copy()
    ct_root_pw = container_root_password()
    env['ROOT_PASSWORD'] = ct_root_pw

    print(os_exec(cmd, env))
    print(os_exec(f'echo "uname -a && ip a && uptime" | pct console {container_id}', shell=True))
    print(f'Root password: {ct_root_pw}')


def update_container(container_id):
    print(os_exec(f'echo "apk update && apk version" | pct console {container_id}', shell=True))
    print(os_exec(f'echo "apk upgrade" | pct console {container_id}', shell=True))


def main():
    alpine_newest_image_name = update_lxc_templates()
    # TODO: translate image names not just for local storage?
    image_path = f'/var/lib/vz/template/cache/{alpine_newest_image_name}'
    create_container(300, 'testct', image_path)
    update_container(300)


if __name__ == '__main__':
    main()
