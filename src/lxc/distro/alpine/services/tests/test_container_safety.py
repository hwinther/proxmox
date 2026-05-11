from unittest import TestCase
from unittest.mock import patch

from lxc.actions import Container
from lxc.distro.alpine.actions import AlpineContainer


class _FakeLxcNode:
    vmid = 123


class _FakeLxcConfig:
    lxc_node = _FakeLxcNode()


class PctConsoleShellQuotingTests(TestCase):
    def test_pct_console_shell_quotes_inner_command(self):
        container = AlpineContainer(container_id=999)
        injection_attempt = 'echo "hi" && rm -rf /'
        with patch('lxc.actions.os_exec') as mock_exec:
            mock_exec.return_value = ''
            container.pct_console_shell(injection_attempt)
        cmd_arg = mock_exec.call_args.args[0]
        self.assertIn("'echo \"hi\" && rm -rf /'", cmd_arg)
        self.assertIn('| pct console 999', cmd_arg)

    def test_pct_console_shell_handles_single_quotes(self):
        container = AlpineContainer(container_id=42)
        with patch('lxc.actions.os_exec') as mock_exec:
            mock_exec.return_value = ''
            container.pct_console_shell("echo 'a'")
        cmd_arg = mock_exec.call_args.args[0]
        # shlex.quote escapes embedded single quotes via '"'"' bridging
        self.assertIn("'echo '\"'\"'a'\"'\"''", cmd_arg)
        self.assertIn('| pct console 42', cmd_arg)


class ContainerInitValidationTests(TestCase):
    def test_lxc_config_requires_pve_node(self):
        with self.assertRaises(ValueError):
            Container(lxc_config=_FakeLxcConfig(), pve_node=None)

    def test_both_container_id_and_lxc_config_rejected(self):
        with self.assertRaises(ValueError):
            Container(container_id=1, lxc_config=_FakeLxcConfig(), pve_node=object())

    def test_neither_arg_rejected(self):
        with self.assertRaises(ValueError):
            Container()
