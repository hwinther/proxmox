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

*Links*

- [Overview of display devices](https://www.kraxel.org/blog/2019/09/display-devices-in-qemu/)
- TODO: it might be outdated, perhaps make a summary that is specific to this goal here
- [QEMU 3dfx](https://github.com/kjliew/qemu-3dfx)
- [Build DJGPP](https://github.com/andrewwutw/build-djgpp)

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

### Linux 2.2 and framebuffer graphical mode

Linux kernel 2.2 supports SMP (multiprocessor), the "linux up" choice in LILO is the single processor kernel, by default
the SMP version will be used by lilo.
The SMP kernel might have issues related to APIC, to resolve this you should try one of the following

1. Choose `linux-up` in the lilo prompt, and change the default (`default=linux`) in /etc/lilo.conf after booting.
2. Disable APIC by typing `linux noapic` in the lilo prompt, and adding `append="noapic"` to the linux entry in
   /etc/lilo.conf after booting.

*Newer 2.2.x kernels or linux distros using them might automatically disable APIC and APM, so it is not always required
to configure this*
bp
If you updated the /etc/lilo.conf file in the previous step, remember to run lilo afterward.

| Color | 640x480 | 800x600 | 1024x768 | 1280x1024 |
|-------|--------:|--------:|---------:|----------:|
| 256   |   0x301 |   0x303 |    0x305 |     0x307 |
| 32k   |   0x310 |   0x313 |    0x316 |     0x319 |
| 64k   |   0x311 |   0x314 |    0x317 |     0x31A |
| 16M   |   0x312 |   0x315 |    0x318 |     0x31B |

| Color | 640x480 | 800x600 | 1024x768 | 1280x1024 |
|-------|--------:|--------:|---------:|----------:|
| 256   |     769 |     771 |      773 |       775 |
| 32k   |     784 |     787 |      790 |       793 |
| 64k   |     785 |     788 |      791 |       794 |
| 16M   |     786 |     789 |      792 |       795 |

Add vga=775 to the root section to enable framebuffer and set the console resolution to 1280x1024.
Run lilo afterward to update the config.

On most systems the /usr/bin/X11R6/bin/X will be symlinked to the appropriate XF86_Server binary, but on RedHat this is
in /etc/X11/X.
You will want to update this if SVGA or some other driver has already been selected as the default driver, otherwise
you'll need to configure additional parameters and not just use startx to launch X11.
`cd /etc/X11 && rm -f X && ln -s ../../usr/X11R6/bin/XF86_FBDev X`

If you want to add a serial console in lilo.conf then it should look something like
this: `append="console=ttyS1,19200n8 console=tty1"`, you should also add the following line to
/etc/inittab: `S0:23:respawn:/sbin/mingetty -h -L ttyS0 19200 vt100`

TODO: cleanup

- Vga modes https://www.linuxquestions.org/questions/debian-26/lilo-vga-modes-152575-print/
- Copy XF86_FB from http://ftp.xfree86.org/pub/XFree86/3.3.6/binaries/Linux-ix86-glibc20/Servers/ to use FB as device
- https://forums.virtualbox.org/viewtopic.php?t=77226
- https://student.dei.uc.pt/~nemanuel/Documentation/FBD/
- QEMU network list https://en.wikibooks.org/wiki/QEMU/Devices/Network
- [Linux kernel 2.2 VESA FB documentation](https://www.kernel.org/doc/Documentation/fb/vesafb.txt) [1]

### Linux 2.0 and 2.2 network driver

To autoload the NIC driver at boot, add an alias to /etc/modules.conf such as `alias eth0 pcnet32`
On linux kernel 2.0 ne2k-pci seems to work, but it does not seem to be very stable as after prolonged use the interface
stops responding.
On linux kernel 2.2 pcnet32 seems to be the most stable, however it is limited to 10/100mbps.

### RedHat source RPM

RedHat source RPMs can be useful to backport or reconfigure known working and patched versions of older software.
This can be utilized even if the operating system does not natively support RPM, just prepare the build on a RedHat
system first and then transfer the source folder over to the target system.
There have been changes to how this process works over the years,
so I had to do some digging to find the old (pre centos and RHEL) examples.
Before rpmbuild [1], you install the src.rpm and then prepare the build to extract and patch the source files:

```
Install the source code in the SOURCES directory used by RPM (/usr/src/redhat/SOURCES) with this command:
  rpm -ivv realport-version-revision.src.rpm
This command also copies the specification file (/usr/src/redhat/SPECS/realport-version.spec) to the SPECS directory.
Use the RPM tools to open the source archive:
  cd /usr/src/redhat/SPECS
  rpm -bp realport-version.spec
The -bp option specifies that only the preparation section (%prep) of the specification file should be executed. This might result in the source files being uncompressed, removed from the archive, and placed in the following directory:
  /usr/src/redhat/BUILD/realport-version
```

*excerpt from Custom Installation Procedure[2]*

#### Links

- [Red Hat Linux 5.2 with XFCE 2.4.0](https://imgur.com/a/VGECyoI)
- [RH dual boot and laptop config](http://redgrittybrick.org/libretto.html)
- [Corel Linux in QEMU](https://forum.eaasi.cloud/t/corel-linux-in-qemu/64/1) [1]
- [Caldera OpenLinux 13 on QEMU](https://gekk.info/blog/main/installing-caldera-openlinux-13-on-qemu.html)
- [Slackware 3.5](https://virtuallyfun.com/2010/05/12/slackware-3-5/)
    - [Configuration file was copied and stored](templates/x11/XF86Config-Slackware3.5-VGA16)
- [XConfig documentation](http://coffeenix.net/doc/misc/xconfig/)
- [CentOS rebuild source RPM](https://wiki.centos.org/HowTos(2f)RebuildSRPM.html) [1]
- [RedHat installing the driver (source RPM)](https://www.ing.iac.es/~docs/external/realport/rp-linux-conf-install-driver-rpm.html) [2]

### Old BSD

TODO

#### Links

- [FreeBSD with XOrg](https://blog.burghardt.pl/2009/03/freebsd-with-xorg-on-qemu/)

### MS DOS 6, Windows 3.x

TODO: list relevant contents of DOS iso

### Windows 95/98

Install chipset drivers first to have other devices detected (TODO)
Enable DMA for all IDE devices (hd and cdrom) in their properties in device manager

TODO: List relevant contents of DOS iso

#### Links

- [Win9X display driver](https://github.com/camthesaxman/win9x_vm_display_driver)
- [QEMU MESA/GL/#Dfx glide pass-through](https://github.com/kjliew/qemu-3dfx)
- [Build DJGPP](https://github.com/andrewwutw/build-djgpp)

### Wayback browsing

#### Links

- [Wayback Proxy](https://github.com/richardg867/WaybackProxy)
- [Protoweb](https://protoweb.org/wiki/servers/)
