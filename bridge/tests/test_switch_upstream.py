import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "switch_upstream.py"
SPEC = importlib.util.spec_from_file_location("switch_upstream", SCRIPT)
switch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(switch)

PUBLIC_KEY = "upstream-public-key"
DIRECT = "203.0.113.10:51820"
WG_TEXT = f"""[Interface]
Address = 10.10.10.1/24
ListenPort = 51820
PrivateKey = bridge-private-key

[Peer]
PublicKey = client-public-key
AllowedIPs = 10.10.10.5/32

[Peer]
PublicKey = manually-managed-client
PresharedKey = manual-client-psk
AllowedIPs = 10.10.10.4/32

# upstream
[Peer]
PublicKey = {PUBLIC_KEY}
AllowedIPs = 0.0.0.0/0
Endpoint = {DIRECT}

# BEGIN MANAGED CLIENTS
# BEGIN CLIENT alice
### Client alice
[Peer]
PublicKey = alice-public-key
PresharedKey = alice-psk
AllowedIPs = 10.10.10.6/32
# END CLIENT alice

# BEGIN CLIENT bob
### Client bob
[Peer]
PublicKey = bob-public-key
PresharedKey = bob-psk
AllowedIPs = 10.10.10.7/32
# END CLIENT bob
# END MANAGED CLIENTS
"""
OBF_TEXT = """[main]
source-if = 127.0.0.1
source-lport = 51821
target = 203.0.113.10:51821
key = a-unique-test-secret
masking = STUN
fwmark = [CURRENT_WG_FWMARK]
"""


class SwitchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / "config/wg_confs").mkdir(parents=True)
        self.wg_file = root / "config/wg_confs/wg0.conf"
        self.wg_file.write_text(WG_TEXT)
        self.obf_file = root / "wg-obfuscator.conf"
        self.obf_file.write_text(OBF_TEXT)
        self.state_file = root / ".obfuscation-state.json"
        for attr, value in (("ROOT", root), ("WG_CONFIG", self.wg_file),
                            ("OBF_CONFIG", self.obf_file), ("STATE_FILE", self.state_file)):
            patcher = patch.object(switch, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.commands = []

        def fake_wg(*args):
            self.commands.append(args)
            if args == ("show", "wg0", "fwmark"):
                return "0xca6c"
            if args == ("show", "wg0", "peers"):
                return PUBLIC_KEY
            return ""

        self.wg_patcher = patch.object(switch, "docker_wg", side_effect=fake_wg)
        self.wg_patcher.start()
        self.addCleanup(self.wg_patcher.stop)
        self.compose_patcher = patch.object(switch, "run", return_value="true")
        self.compose_run = self.compose_patcher.start()
        self.addCleanup(self.compose_patcher.stop)

    def test_switch_and_one_command_rollback_preserve_managed_clients(self):
        managed_before = WG_TEXT.split("# BEGIN MANAGED CLIENTS", 1)[1]
        manual_before = WG_TEXT.split("[Peer]\nPublicKey = manually-managed-client", 1)[1].split(
            "# upstream", 1
        )[0]
        switch.enable()
        enabled = self.wg_file.read_text()
        self.assertIn("Endpoint = 127.0.0.1:51821", enabled)
        self.assertIn("PersistentKeepalive = 25", enabled)
        self.assertIn("FwMark = 51820", enabled)
        self.assertEqual(enabled.split("# BEGIN MANAGED CLIENTS", 1)[1], managed_before)
        self.assertEqual(
            enabled.split("[Peer]\nPublicKey = manually-managed-client", 1)[1].split(
                "# upstream", 1
            )[0], manual_before
        )
        self.assertIn("fwmark = 51820", self.obf_file.read_text())
        self.assertEqual(self.state_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.obf_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.compose_run.call_count, 2)

        switch.disable()
        self.assertEqual(self.wg_file.read_text(), WG_TEXT)
        self.assertFalse(self.state_file.exists())
        self.assertIn(("set", "wg0", "peer", PUBLIC_KEY, "endpoint", DIRECT,
                       "persistent-keepalive", "0"), self.commands)

    def test_refuses_mismatched_active_mark_before_starting_obfuscator(self):
        self.wg_file.write_text(WG_TEXT.replace("PrivateKey = bridge-private-key",
                                                "PrivateKey = bridge-private-key\nFwMark = 0xdead"))
        with self.assertRaisesRegex(switch.SwitchError, "отличается"):
            switch.enable()
        self.compose_run.assert_not_called()
        self.assertFalse(self.state_file.exists())

    def test_reenable_keeps_original_rollback_address(self):
        switch.enable()
        switch.enable()
        self.assertEqual(switch.read_state()["direct_endpoint"], DIRECT)
        self.assertEqual(self.compose_run.call_count, 4)
        switch.disable()
        self.assertEqual(self.wg_file.read_text(), WG_TEXT)

    def test_live_switch_error_restores_direct_config(self):
        original_wg = switch.docker_wg

        def fail_local_set(*args):
            if args[:3] == ("set", "wg0", "peer") and switch.LOCAL_ENDPOINT in args:
                raise switch.SwitchError("simulated wg failure")
            return original_wg(*args)

        with patch.object(switch, "docker_wg", side_effect=fail_local_set):
            with self.assertRaisesRegex(switch.SwitchError, "simulated"):
                switch.enable()
        self.assertEqual(self.wg_file.read_text(), WG_TEXT)
        self.assertEqual(switch.read_state()["direct_endpoint"], DIRECT)


if __name__ == "__main__":
    unittest.main()
