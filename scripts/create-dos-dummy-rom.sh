#!/bin/sh
python2.7 -c 'import sys; sys.stdout.write("\x55\xaa\xc8\xcb\x6e" + "\x00"*(100*1024 - 5))' > /usr/share/kvm/dummy.rom
