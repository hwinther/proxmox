# proxmox

## Floppy drives

Combine multiple floppy images to one:

```
mkdir /tmp/win31 # and copy all images there
mkdir /mnt/tmpflp

mount -o loop /tmp/win31/Disk01.img /mnt/tmpflp/ && cp -i /mnt/tmpflp/* . && umount /mnt/tmpflp
mount -o loop /tmp/win31/Disk02.img /mnt/tmpflp/ && cp -i /mnt/tmpflp/* . && umount /mnt/tmpflp
# repeat for all floppies
```

Create new floppy image:
```
# Normal floppy image size, 1.4mb
mkfs.msdos -C /tmp/combined.img 1440

# Extended floppy size, adjust to fit the data in combination folder, with floppy name HCW
mkfs.msdos -C /tmp/combined.img 5760 -n HCW
```

## ISO / CDROM images
```
# Create default ISO layout and character set, typically smallest common denominator (8 char length, caps insensitive?)
# similar to FAT16 but supports a little more I think (TODO: fact checks)
mkisofs -o win31-inst.iso /root/win31-iso/

mkisofs -iso-level 4 -o win95_games.iso win95_games

mkisofs -l -o dos_drivers.iso dosdrivers/
```
