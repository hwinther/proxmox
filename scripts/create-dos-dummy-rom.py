#!/usr/bin/python3
import sys
with open('/usr/share/kvm/dummy.rom', 'wb') as rom_file:
    rom_file.write(b'\x55\xaa\xc8\xcb\x6e' + b'\x00'*(100*1024 - 5))
