# Various useful bash snippets for linux hosts and guests

## Debian

### Debian system update and upgrade

```bash
# Full upgrade and clean unused and cached packages
apt update && apt full-upgrade && apt autoremove && apt autoclean

# If you're going to upgrade to a newer version of debian, then you should run the above full-upgrade command *before* changing the sources list files

# Upgrade buster to bullseye
sed -i 's/buster\/updates/bullseye-security/g;s/buster/bullseye/g' /etc/apt/sources.list
sed -i -e 's/buster/bullseye/g' /etc/apt/sources.list.d/*

# Upgrade bullseye to bookworm
sed -i 's/bullseye/bookworm/g' /etc/apt/sources.list
sed -i -e 's/bullseye/bookworm/g' /etc/apt/sources.list.d/*

# After updating sources - new install packages without removing old ones
apt update && apt upgrade --without-new-pkgs
# Then perform a full upgrade
apt full-upgrade
# Then reboot
reboot

# Purge old/residual config packages in debian:
dpkg -l | grep '^rc' | wc -l
dpkg -l | grep '^rc' | awk '{print $2}' | xargs dpkg --purge
```

### Disk operations

```bash
# If the root storage medium was changed from e.g. sda to nvme0, reconfigure grub and select the new boot disk
dpkg-reconfigure grub-pc
```

### Unattended upgrades and local mail configuration

```bash
# Install unattended upgrades (automatic patching)
apt install unattended-upgrades apt-listchanges

# Add mail notifications of unattended upgrades
nano /etc/apt/apt.conf.d/50unattended-upgrades
# Uncomment or edit the following:
Unattended-Upgrade::Mail "root";

# Verify
unattended-upgrade -d
```

### Local mail forwarding

```bash
# Install postfix and reconfigure it
apt install postfix

# Select the smarthost/relay profile
dpkg-reconfigure postfix

# Alias/rewrite mail for root to system admin
echo /.+@.+/ hc@wsh.no > /etc/postfix/virtual-regexp
postmap /etc/postfix/virtual-regexp

nano /etc/postfix/main.cf
# add this:
virtual_maps = regexp:/etc/postfix/virtual-regexp

/etc/init.d/postfix reload

nano /etc/passwd
# set root description to root@hostname

# Verify
echo $HOSTNAME | mail hc@wsh.no
```

### IPv6

```bash
# Get IPv6 address from ISP dhcp with prefix delegation
dhclient -v -6 -P wan

# Disable IPv6 🥹
nano /etc/sysctl.conf

# Add to the bottom of the file:
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1
net.ipv6.conf.lo.disable_ipv6=1

# Verify (activate config without reboot)
sysctl -p
```

### WIFI hacks

```bash
# Set broadcom wifi to monitor mode
echo 1 | sudo tee /proc/brcm_monitor0
```

### Install Zabbit agent

```bash
# Find the newest debian package that matches your debian version and download it
wget https://repo.zabbix.com/zabbix/4.4/debian/pool/main/z/zabbix-release/zabbix-release_4.4-1+buster_all.deb
dpkg -i zabbix-release_4.4-1+buster_all.deb
rm -f zabbix-release_4.4-1+buster_all.deb

# Or from the package repo?
apt update && apt install zabbix-agent

systemctl enable zabbix-agent
systemctl start zabbix-agent
```

## Alpine

### Alpine system update and upgrade

```bash
# Update
apk update && apk upgrade

# Upgrade to newer alpine version
sed -i 's/v3.17/v3.18/g' /etc/apk/repositories
apk update && apk upgrade
```

### New host initial setup

```bash
apk update && apk upgrade && apk add nano

tee /etc/profile.d/dg_color_prompt.sh >/dev/null <<KEK
PS1='${debian_chroot:+($debian_chroot)}\[\033[01;31m\]\u\[\033[01;33m\]@\[\033[01;36m\]\h \[\033[01;33m\]\w \[\033[01;35m\]\$ \[\033[00m\]'
KEK

# Install openssh
apk add openssh openssh-server && rc-update add sshd # openssh client and server

# Install bind9
apk add bind && rc-update add named
# After configuring, start it with
rc-service named start

# Install ISC dhcpd
apk add dhcp-server-vanilla && rc-update add dhcpd
# After configuring, start it with
rc-service isc-dhcp-server start
```

## PVE - Proxmox virtualization environment

### Cluster

```bash
# Fix cluster desynced node
systemctl stop pve-cluster.service
pmxcfs -l
scp root@host-in-cluster:/etc/pve/corosync.conf /etc/pve/corosync.conf
killall -9 pmxcfs
systemctl start pve-cluster.service
pvecm status
```

## PBS - Proxmox backup server

### Initial setup

```bash
USER1="user1"
USER1_EMAIL="user1@gmail.com"
USER2="user2"
USER2_EMAIL="user2@gmail.com"

zpool create -o ashift=12 primary mirror sdb sdc
zfs set compression=on primary
zfs create -o mountpoint=/mnt/datastore/$USER1 primary/$USER1
zfs create -o mountpoint=/mnt/datastore/$USER2 primary/$USER2

# zfs list
NAME               USED  AVAIL     REFER  MOUNTPOINT
primary            936K  7.14T       96K  /primary
primary/USER1      96K  7.14T        96K  /mnt/datastore/USER1
primary/USER2      96K  7.14T        96K  /mnt/datastore/USER2

proxmox-backup-manager user create $USER1@pbs --email $USER1_EMAIL --password `openssl rand -base64 32`
proxmox-backup-manager user create $USER2@pbs --email $USER2_EMAIL --password `openssl rand -base64 32`

proxmox-backup-manager datastore create $USER1 /mnt/datastore/$USER1 --notify-user $USER1@pbs
proxmox-backup-manager datastore create $USER2 /mnt/datastore/$USER2 --notify-user $USER2@pbs

proxmox-backup-manager user generate-token $USER1@pbs sync
proxmox-backup-manager user generate-token $USER2@pbs sync

# We also need this for remote sync:
proxmox-backup-manager acl update /datastore/$USER1 DatastoreBackup --auth-id $USER1@pbs
proxmox-backup-manager acl update /datastore/$USER2 DatastoreBackup --auth-id $USER2@pbs
```

### New section template

```bash
# Stuff
```
