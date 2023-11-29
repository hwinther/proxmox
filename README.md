# Proxmox Virtual Environment - IAC and notes

## Building image files for mounting to VM

### Floppy drives

Combine multiple floppy images to one:

```bash
mkdir /tmp/win31 # and copy all images there
mkdir /mnt/tmpflp

mount -o loop /tmp/win31/Disk01.img /mnt/tmpflp/ && cp -i /mnt/tmpflp/* . && umount /mnt/tmpflp
mount -o loop /tmp/win31/Disk02.img /mnt/tmpflp/ && cp -i /mnt/tmpflp/* . && umount /mnt/tmpflp
# repeat for all floppies
```

Create new floppy image:

```bash
# Normal floppy image size, 1.4mb
mkfs.msdos -C /tmp/combined.img 1440

# Extended floppy size, adjust to fit the data in combination folder, with floppy name HCW
mkfs.msdos -C /tmp/combined.img 5760 -n HCW
```

### ISO / CDROM images

```bash
# Create default ISO layout and character set, typically smallest common denominator (8 char length, caps insensitive?)
# similar to FAT16 but supports a little more I think (TODO: fact checks)
mkisofs -o win31-inst.iso /root/win31-iso/

mkisofs -iso-level 4 -o win95_games.iso win95_games

mkisofs -l -o dos_drivers.iso dosdrivers/
```

## LXC creation

```bash
export ROOTPASS=testpassword
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGzYkv5+lko9E5Tpc3wHg1ZDm4DZDo/ahtljV3xfiHhf ed25519-key-20171113" > container_authorized_keys

pct create 300 /var/lib/vz/template/cache/alpine-3.17-default_20221129_amd64.tar.xz --hostname testct --memory 128 --swap 128 --net0 name=eth0,bridge=vmbr0,firewall=1,ip=dhcp,type=veth --storage local --rootfs local:0.1 --unprivileged 1 --pool Testing --ssh-public-keys container_authorized_keys --ostype alpine --password="$ROOTPASS" --cmode shell --cores 2 --start 1 --mp0 volume=local:0.01,mp=/etc/testconfig,backup=1,ro=0,shared=0

# pct status 300
status: running

# echo "uname -a" | pct console 300
Linux testct 6.1.15-1-pve #1 SMP PREEMPT_DYNAMIC PVE 6.1.15-1 (2023-03-08T08:53Z) x86_64 Linux

# pct mount 300
mounted CT 300 in '/var/lib/lxc/300/rootfs'

# push file to ct
echo test > /tmp/file.cfg
pct push 300 /tmp/file.cfg /etc/testconfig/file.cfg

# pull file from ct
pct pull 300 /etc/testconfig/file.cfg /tmp/file.cfg
```

## QEMU old OS guide

To emulate an old operating system you usually have to choose an older cpu such as pentium2 with single socket and core,
the i440fx machine + SeaBIOS, default controller with IDE drive(s) and relatively small disks and RAM - typically max
32GB/512MB.
The network card can be Realtek RTL8139 in most cases, but some systems may require ne2k_pci - see an example below.

### Old linux XF86Config

*Working steps for local or vnc based desktop on RedHat 5.2 as of 28.11.2023*

If you select the CIRRUS chipset during install it should autodetect most of the options [1],
if not choose "Cirrus Logic GD544x".
You can also add one or more serial ports as either a backup console or network interface.

*PVE VM configuration*

```yaml
vga: cirrus,memory=8
net0: ne2k_pci=00:11:22:33:44:55,bridge=vmbr0
```

```bash
# To (re)configure X in a similar fashion to the original installer (easier) then run
Xconfigurator

# The more old fashioned graphical configuration provided by XF86 can be launched with
XF86Setup
```

*If the X server starts but the display freezes then try adding these options to the Device section [1]*

```
Section "Device"
   ...
   Option "no_bitblt"
   Option "noaccel"
   Option "sw_cursor"
```

#### Links

- [Red Hat Linux 5.2 with XFCE 2.4.0](https://imgur.com/a/VGECyoI)
- [RH dual boot and laptop config](http://redgrittybrick.org/libretto.html)
- [Corel Linux in QEMU](https://forum.eaasi.cloud/t/corel-linux-in-qemu/64/1) [1]

### Old BSD

TODO

#### Links

- https://blog.burghardt.pl/2009/03/freebsd-with-xorg-on-qemu/

### MS DOS 6, Windows 3.x

TODO: list relevant contents of DOS iso

### Windows 95/98

TODO: List relevant contents of DOS iso
