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
mkfs.msdos -C /tmp/combined.img 5760 -n TEST
mount -o loop /tmp/combined.img /mnt/tmpflp
copy file1 file2 file3 /mnt/tmpflp/
umount /mnt/tmpflp
```

QEMU monitor commands:

```bash
# mount new image as floppy0 (A:)
change floppy0 /tmp/Disk1.img
```

### ISO / CDROM images

```bash
# Create default ISO layout and character set, typically smallest common denominator (8 char length, caps insensitive?)
# similar to FAT16 but supports a little more I think (TODO: fact checks)
mkisofs -o win31-inst.iso /root/win31-iso/

mkisofs -iso-level 4 -o win95_games.iso win95_games

mkisofs -l -o dos_drivers.iso dosdrivers/
mkisofs -l -o dos_games.iso dos_games/
```

## LXC creation

```bash
export ROOTPASS=testpassword
echo "ssh-ed25519 AAAA... ed25519-replace-me" > container_authorized_keys

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

- [Overview of QEMU display devices](https://www.kraxel.org/blog/2019/09/display-devices-in-qemu/)
- [Overview of QEMU network devices](https://en.wikibooks.org/wiki/QEMU/Devices/Network)

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

```conf
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

| Color    | 640x480 | 800x600 | 1024x768 | 1280x1024 | 1600x1200 |
|----------|--------:|--------:|---------:|----------:|----------:|
| 8 / 256  |   0x301 |   0x303 |    0x305 |     0x307 |     0x31C |
| 15 / 32k |   0x310 |   0x313 |    0x316 |     0x319 |     0x31D |
| 16 / 64k |   0x311 |   0x314 |    0x317 |     0x31A |     0x31E |
| 24 / 16M |   0x312 |   0x315 |    0x318 |     0x31B |     0x31F |

Older lilo versions can't convert the hexadecimal representation and must be configured with decimal values, so here is
the same table with decimal values:

| Color    | 640x480 | 800x600 | 1024x768 | 1280x1024 | 1600x1200 |
|----------|--------:|--------:|---------:|----------:|----------:|
| 8 / 256  |     769 |     771 |      773 |       775 |       796 |
| 15 / 32k |     784 |     787 |      790 |       793 |       797 |
| 16 / 64k |     785 |     788 |      791 |       794 |       798 |
| 24 / 16M |     786 |     789 |      792 |       795 |       799 |

*256 = 8 bits, 32k = 15 bits, 65k = 16 bits, 16M = 24 bits, 32bits is not typically used, but it would mask out the
extra 8 bits and fit the bus width better. 15 bit is not supported by XF86_FBDev*

Add `vga=775` to the root section to enable framebuffer and set the console resolution to 1280x1024.
Run lilo afterward to update the config.

On most systems the /usr/bin/X11R6/bin/X will be symlinked to the appropriate XF86_Server binary, but on RedHat this is
in /etc/X11/X.
You will want to update this if SVGA or some other driver has already been selected as the default driver, otherwise
you'll need to configure additional parameters and not just use startx to launch X11.
`cd /etc/X11 && rm -f X && ln -s ../../usr/X11R6/bin/XF86_FBDev X`

You can use the template in `templates/x11/XF86Config-3-FBDev` to get started with XF86-FBDev, it will use the
resolution set at boot, but you have to specify the bit depth if it doesn't match the default (8),
e.g. `startx -- -bpp 16`

If you for whatever reason spend a lot of time to compile kernel 2.2.x into a 2.0.x system, you will need to reuse the
kernel include folder in the XF86 include path, it should suffice to symlink e.g.
/usr/src/kernel-2.2.26-custom/include/{linux,video} to /usr/src/redhat/BUILD/XFree86-3.3.3.1/xc/exports/include/.
You will also need to create the devices manually as that is normally done by the RPM or similar installer:

```bash
mknod /dev/fb0 c 29 0
mknod /dev/fb1 c 29 32
mknod /dev/fb2 c 29 64
...
mknod /dev/fb7 c 29 224
```

The amount of devices that are currently active can be found via `cat /proc/fb`

And create the xserver pam.d file if it does not exist:

```bash
cat > /etc/pam.d/xserver
#%PAM-1.0
auth       sufficient   /lib/security/pam_rootok.so
auth       required     /lib/security/pam_console.so
account    required     /lib/security/pam_permit.so
```

If you want to add a serial console in lilo.conf then it should look something like
this: `append="console=ttyS1,19200n8 console=tty1"`, you should also add the following line to
/etc/inittab: `S0:23:respawn:/sbin/mingetty -h -L ttyS0 19200 vt100`

TODO: test VMware SVGA device in RedHat 7.0
TODO: try out an alternative, remote X to
windows: <http://www.straightrunning.com/XmingNotes/>
and configuration details from <https://unix.stackexchange.com/questions/407022/trying-to-run-an-old-version-of-redhat>

- [Kernel vesafb documentation](https://www.kernel.org/doc/Documentation/fb/vesafb.txt)
- [Kernel SVGA documentation which covers the vga boot flag](https://www.kernel.org/doc/Documentation/svga.txt)
- [XF86Config demystified](http://coffeenix.net/doc/misc/xconfig/#bpp)
- Vga modes <https://www.linuxquestions.org/questions/debian-26/lilo-vga-modes-152575-print/>
- [XFree86 3.3.6 FBDev server download](http://ftp.xfree86.org/pub/XFree86/3.3.6/binaries/Linux-ix86-glibc20/Servers/)
- [Forum thread related to RedHat graphics settings in QEMU](https://forums.virtualbox.org/viewtopic.php?t=77226)
- [FBDev/fb guide](https://student.dei.uc.pt/~nemanuel/Documentation/FBD/)
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

```conf
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

- [RedHat Linux 5.2 with XFCE 2.4.0](https://imgur.com/a/VGECyoI)
- [RedHat dual boot and laptop config](http://redgrittybrick.org/libretto.html)
- [Corel Linux in QEMU](https://forum.eaasi.cloud/t/corel-linux-in-qemu/64/1) [1]
- [Caldera OpenLinux 13 on QEMU](https://gekk.info/blog/main/installing-caldera-openlinux-13-on-qemu.html)
- [Slackware 3.5](https://virtuallyfun.com/2010/05/12/slackware-3-5/)
- [Configuration file was copied and stored](templates/x11/XF86Config-Slackware3.5-VGA16)
- [XConfig documentation](http://coffeenix.net/doc/misc/xconfig/)
- [CentOS rebuild source RPM](https://wiki.centos.org/HowTos(2f)RebuildSRPM.html) [1]
- [RedHat installing the driver (source RPM)](https://www.ing.iac.es/~docs/external/realport/rp-linux-conf-install-driver-rpm.html) [2]
- [Linux kernel repository and tgz download](https://kernel.googlesource.com/pub/scm/linux/kernel/git/history/history/+/refs/tags/2.2.0)

### Old BSD

TODO

#### Links

- [FreeBSD with XOrg](https://blog.burghardt.pl/2009/03/freebsd-with-xorg-on-qemu/)

### MS DOS 6, Windows 3.x

TODO: list relevant contents of DOS iso

### Memory tips

Use checkit or scandma? to check memory allocation/usage
Use mem /a/c to see the overview

#### Links

- [MS-DOS 6.22 optimized config example](https://www.vogons.org/viewtopic.php?t=39252)
- [MSDOS tips and tricks](https://www.mdgx.com/31.htm)
- [Smartdrv alternatives](https://www.vogons.org/viewtopic.php?t=19354)
- [MSDOS binary patching](https://www.kennedysoftware.ie/products.htm#td)
- [UIDE](https://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/distributions/1.2/repos/pkg-html/uide.html)
- [UIDE doc](https://home.mnet-online.de/willybilly/fdhelp-internet/en/hhstndrd/base/uide.htm)
- [shsucd (mscdex replacement)](http://adoxa.altervista.org/shsucdx/)
- [shsucdx](http://optimizr.dyndns.org/dos/shsucdx.html)
- [xmgr/xdvd2](http://optimizr.dyndns.org/dos/drivers.html)
- [partitioning of config.sys and autoexec.bat](http://www.abandonia.com/vbullet/showthread.php?t=6991)
- [partitioning of config](https://forum.vcfed.org/index.php?threads/ansi-sys-causes-system-to-hang.79278/)
- [partitioning #2](https://www.philscomputerlab.com/ms-dos-starter-pack.html)
- [msdos memory tips](https://www.mdgx.com/mem6.htm)
- [msdos switches tips](https://www.mdgx.com/last4.htm#SWS)
- [configuration notes for dos w98se and iso bios](https://flaterco.com/kb/DOS_W98SE_general.html)
- [msdos resource downloads](http://manmrk.net/tutorials/DOS/msdos.htm)
- [more utilities downloads](http://annex.retroarchive.org/cdrom/smsw-vol3/UTILS/index.html)
- [DOS ipx networking](https://www.vogons.org/viewtopic.php?t=64789)
- [guide on msdos ram structure](https://virtuallyfun.com/2021/08/03/conventional-ram-aka-that-old-foe/)
- [blog post of various virtualized windows installs - very useful and detailed](https://www.gekk.info/articles/dosapps.html#Windows_1.0)

### Windows 95/98

Install chipset drivers first to have other devices detected (TODO)
Enable DMA for all IDE devices (hd and cdrom) in their properties in device manager

TODO: List relevant contents of DOS iso

Before installing, either use
patch9x (`-drive file=/var/lib/vz/template/iso/patcher9x-0.8.50-boot.img,if=floppy,index=0 -boot a`) on the installation
media
or reduce host cpu frequency
via `cpupower frequency-set -u 1G`.

To install Windows 98 SE add the boot floppy image and the cdrom iso file:

```conf
args: -drive file=/var/lib/vz/template/iso/Windows_98_Second_Edition_Boot.img,if=floppy,index=0 -boot a
ide1: local:iso/EN_WIN98SE_115_OEM_WPLUS.ISO,media=cdrom,size=632374K

scsi0: local-lvm:vm-900-disk-0,size=4G
scsihw: lsi
```

And then run fdisk and format to create your new system volume:

TODO: script the whole thing in two bat files, stage0 and stage1 to automate the process

```shell
fdisk

(or one liner)

fdisk /fprmt
fdisk 1 /pri:4095
```

Then copy over the win98 files to the newly formatted volume and add the win9x display++ drivers from dosdrivers.iso to
the same folder so that they can be detected and installed without selecting a path later.
There is also a script that will make the installation mostly unattended in this folder.
Launch setup with the /nm (ignore hardware demand) and /pj (force use of ACPI/PnP)

```shell
d:\win98\format C:
set PATH=%PATH%;d:\tools\oldmsdos
xcopy32 /E d:\win98\ c:\win98\

c:
cd win98
xcopy32 e:\win9x\vmdisp9x\*.*
setup /nm /pj
```

#### Links

- [Win9X display driver](https://github.com/camthesaxman/win9x_vm_display_driver)
- [QEMU MESA/GL/#Dfx glide pass-through](https://github.com/kjliew/qemu-3dfx)
- [Build DJGPP](https://github.com/andrewwutw/build-djgpp)

### OS/2 Warp 4

Warp 4.0 installation stopped at the final installation floppy due to an unknown issue.
Warp 4.52 installs from bootable iso with IDE disk and cdrom, and spice with attached audio drivers (sb16, adlib and pc speaker).
With cirrus-vga over VNC (and audio over VNC once that is available in free clients), higher resolutions should be possible.

#### Links

- [SciTech display doctor](https://forums.virtualbox.org/viewtopic.php?t=82709)
- [Drivers and firefox install](https://lantian.pub/en/article/modify-computer/os2-warp-firefox.lantian/)

### Solaris 2.x on SPARC

qemu-system-sparc is 32 bit and supports the SS-5 machine with typically sub 200mhz cpus and max 512 mb ram
qemu-system-sparc64 supports - TODO

OpenBios exists for both platforms and will simplify configuring boot on the command line, here are some configuration examples:

xxx TODO

Alternatively there are BIOS'es that have been dumped from EPROM which can be found in the SPARC BIOS collection [1]:

| Image name | System name |
| ---------- | ----------- |
| cpu10.bin | x |
| cpu24.bin | x |
| ipc.bin | SPARCstation IPC |
| lx.bin | SPARCstation LX |
| lx564.bin | SPARCstation LX |
| ross225r.bin | x |
| ss10_v2.25_rom | SPARCstation 10 |
| ss20_v2.25_rom | SPARCstation 20 |
| ss4.bin | SPARCstation 4 |
| ss5-170.bin | SPARCstation 5 |
| ss5.bin | SPARCstation 5 |
| ss600mp.bin | SPARCserver 600MP |
| voyager.bin | SPARCstation Voyager |

An example of using SPARCstation 5 BIOS:

```bash
# SPARCstation 5 expects the disk to be scsi target 3 and cdrom to be scsi target 6, and have max 256MB ram and a single CPU.
# To properly emulate a SUN cdrom we use a physical block size of 512.
qemu-system-sparc \
 -drive file=disk0.raw,if=none,id=drive-scsi0,format=raw,cache=none,aio=io_uring,detect-zeroes=on \
 -device scsi-hd,scsi-id=3,drive=drive-scsi0,id=scsi0 \
 -drive file=sun-solaris-8-0101-installation-sparc.iso,if=none,id=drive-scsi1,media=cdrom,aio=io_uring \
 -device scsi-cd,scsi-id=6,drive=drive-scsi1,id=scsi1,physical_block_size=512 \
 -machine accel=tcg,type=SS-5 -cpu "TI SuperSparc 60" \
 -m 256 \
 -vga cg3 -g 1024x768x8 -monitor stdio \
 -bios ss5.bin

# If graphical install fails, you can switch the -vga line with the following to install the OS over serial terminal:
# -nographic -vga none -serial mon:stdio \

# Use 'sendkey stop-a' in monitor if it goes into a boot retry loop
# Use probe-scsi to verify the scsi ids or devalias to see device aliases in the nvrom
# Use module-info to see cpu and bus speeds

# Type 'boot cdrom:d' to boot the d partition of the cdrom iso

# If cdrom installation fails, you can try again via boot disk3:b

# Type 'boot sd()' to boot the first partition of the primary disk
```

#### Tips

- Use monitor and sendkey to break if you're stuck trying to boot from network for instance: `sendkey stop-a`
- Serial terminal seems to conflict with sendkey stop-a, but if you disconnect the network interface the BIOS might skip network boot and go to the prompt.
- An 8GB virtual disk can be formatted with the following parameters; type 18, data cylinders 16200, alternative cylinders 2, physical cylinders 16202, heads 16, data sectors 60, rpm 3600, disk type name Qemu8G, everything else default
- Otherwise use a 2GB, 2.1GB or 3GB vm disk and use the SUN1.3, SUN2.1G or SUN2.9G disk layout, respectively.
- Solaris 2.4/2.5 (and probably older) need the cdrom to be identified as a scsi-hd in order to boot the installation environment from it. You can change -device scsi-cd to scsi-nd and add readonly=true to the drive parameter.
- The Solaris 2.5 installer will spend a long time without any output but it should finish eventually.
- Solaris 2.x should be fine with 3GB, but solaris 8 needs over 3GB so use the 8G template. Solaris 9, 10 and 11 probably need even more if every package is to be installed.
- TODO: add template raw disk 3G + 8G to repo
- Solaris 9 can install from a dvd iso, but ss5.bin does not seem to work, use OpenBIOS32 instead

#### Sun/Oracle installation guides

- [Solaris 2.4](https://docs.oracle.com/cd/E19457-01/801-6610/801-6610.pdf)

#### SPARC 64

```bash
# sparc64 support seems to be pretty limited, in order to boot from cdrom you either have to use the "-boot d" argument or type "boot cdrom:f" in the OpenBIOS prompt.

# Create a raw disk image first, then the machine can be started with the following:
ISO=/var/lib/vz/templates/iso/NetBSD-9.3-sparc64.iso
sudo /usr/bin/qemu-system-sparc64 -drive file=hd.raw,if=none,id=drive-ide0-0-1,format=raw,cache=none -device ide-hd,bus=ide.0,unit=0,drive=drive-ide0-0-1,id=ide0-0-1 -serial pty -monitor stdio -boot c -machine sun4u -netdev type=tap,id=net0,ifname=tap0,script=no,downscript=no -device sunhme,mac=BC:24:11:47:EA:AA,netdev=net0,bus=pciB -cdrom $ISO -nographic

# ne2k_pci can be used instead of sunhme, but it will be limited to 10mbps and it might be less stable

# Then open the serial terminal in another window, e.g.:
miniterm -D /dev/pts/8

# Attaching the network interface manually (it should be configured via a script), can be done like this:
ovs-vsctl add-port vmbr0 tap0
ip link tap0 up
```

#### Links

- [Official QEMU SPARC platform documentation](https://wiki.qemu.org/Documentation/Platforms/SPARC)
- [Wikipedia overview of SPARCstation variants](https://en.wikipedia.org/wiki/SPARCstation)
- [SPARC BIOS collection](https://github.com/hwinther/sparc/tree/additional-images-from-itomato-NeXTSPARC) [1]
- [Ongoing issue related to trap 0x29 data access error with S5](https://gitlab.com/qemu-project/qemu/-/issues/2017)
- [NetInstall solaris from linux server](https://www.cs.toronto.edu/~cvs/unix/Solaris-Linux-NetInstall.html)
- [How to use floppy disks with solaris](https://people.cs.rutgers.edu/~watrous/floppies-under-solaris.html)
- [Solaris 2.6 SPARC on QEMU guide](https://learn.adafruit.com/build-your-own-sparc-with-qemu-and-solaris/create-a-disk-image)
- [Oracle booting and shutting down Solaris systems](https://docs.oracle.com/cd/E37838_01/html/E60978/gkkvd.html)
- [Working with Openboot](https://tldp.org/HOWTO/SPARC-HOWTO-14.html)
- [Installing NetBSD on SPARC](https://cdn.netbsd.org/pub/NetBSD/NetBSD-9.2/sparc/INSTALL.html)
- [Potential solution to cd boot crash via reformatting ISO as disk](https://forum.winworldpc.com/discussion/12876/stupid-solaris-2-3-2-5-1-installation-problems-question)
- [Disk size calculator](http://www.csgnetwork.com/mediasizecalc.html)
- [Wayback machine - Sun solaris format guide](https://web.archive.org/web/20080228035934/http://www.sun.com/bigadmin/content/submitted/format_utility.jsp)
- [Formatting disks for Solaris](https://virtuallyfun.com/2010/10/03/formatting-disks-for-solaris/)
- [Running Solaris 2.6 under QEMU on Mint](https://astr0baby.wordpress.com/2018/09/22/running-solaris-2-6-sparc-on-qemu-system-sparc-in-linux-x86_64-mint-19/)
- [SunOS 4.1.4 SPARC on QEMU](http://defcon.no/sysadm/playing-with-sunos-4-1-4-on-qemu/)
- [Running SunOS 4 in QEMU with X11 forwarding](https://john-millikin.com/running-sunos-4-in-qemu-sparc)
- [Build your own sparc with qemu and solaris](https://learn.adafruit.com/build-your-own-sparc-with-qemu-and-solaris/install-solaris-part-2)
- [SunOS 4.1 device addressing thread](https://qemu-discuss.nongnu.narkive.com/qDJ6e4WX/qemu-system-sparc-what-would-i-need-to-change-to-add-functionality-to-save-the-nvram-content)
- [Driver information/experiences](http://pci.unsupported.info/)

### Wayback browsing

#### Links

- [Wayback Proxy](https://github.com/richardg867/WaybackProxy)
- [Protoweb](https://protoweb.org/wiki/servers/)

## Dialup ISP emulation

### Links

- [Hayes AT command set (overview)](https://en.wikipedia.org/wiki/Hayes_AT_command_set)
- [Hayes AT command set (more details)](https://www.activexperts.com/serial-port-component/at/hayes/#ATSETPART1)
- [(when using unix socket to connect serial) how to find which process is connected](https://unix.stackexchange.com/questions/16300/whos-got-the-other-end-of-this-unix-socketpair)
