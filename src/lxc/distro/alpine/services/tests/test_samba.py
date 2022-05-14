from unittest.case import TestCase

from lxc.distro.alpine.services.samba import SAMBA_SHARE_HOMES, SambaShare


class SambaTests(TestCase):
    def test_samba_config(self):
        samba_share = SambaShare(name='test', path='/tmp/test')
        self.assertEqual("""
[test]
  path = /tmp/test
  guest ok = no
  browseable = no
  read only = yes
  printable = no
""", samba_share.generate_config_section())

        samba_share_homes = SAMBA_SHARE_HOMES
        self.assertEqual("""
[homes]
  path = 
  comment = Home Directories
  create mask = 700
  directory mask = 700
  valid users = %S
  guest ok = no
  browseable = no
  read only = yes
  printable = no
""", samba_share_homes.generate_config_section())
