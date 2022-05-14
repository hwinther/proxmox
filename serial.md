python3 ../../scripts/at.py /var/run/qemu-server/102.serial0

ln -s /usr/bin/slirp ./slirp-nandhp-patch
./tools/atduck/atduck unix:/var/run/qemu-server/102.serial0
