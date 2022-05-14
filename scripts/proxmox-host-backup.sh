#!/bin/sh
# Add the following line with the correct password to your .bashrc:
# export PBS_PASSWORD=c24a9409-dead-beef
proxmox-backup-client backup root.pxar:/ --exclude /var/lib/vz/ --exclude /var/log/journal --exclude /mnt --exclude /tmp --exclude /var/tmp --repository 'hwinther@pbs!sync@pbs.oh.wsh.no:hwinther'
