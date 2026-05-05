import importlib.util
import json
import shlex
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FLEET_PATH = ROOT / "scripts" / "fleet.py"

spec = importlib.util.spec_from_file_location("fleet", FLEET_PATH)
fleet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fleet)


class FleetTests(unittest.TestCase):
    def test_configure_firewall_does_not_treat_inactive_ufw_as_active(self):
        calls = []

        def fake_ssh(host, cmd, timeout=30, check=True):
            calls.append(cmd)
            if cmd.startswith("ufw status"):
                return "Status: inactive"
            if cmd.startswith("iptables -L INPUT"):
                return "Chain INPUT (policy ACCEPT)"
            return ""

        with patch.object(fleet, "ssh", fake_ssh):
            fleet.configure_firewall("node1", [443, 9453])

        self.assertFalse(any(cmd.startswith("ufw allow") for cmd in calls))
        self.assertFalse(any(cmd.startswith("ufw reload") for cmd in calls))

    def test_create_inbound_shell_quotes_remote_script_args(self):
        captured = {}

        def fake_ssh_script(host, script_text, args="", timeout=60):
            captured["args"] = args
            return json.dumps({"success": True, "uuid": "uuid", "public_key": "pub", "short_id": "sid", "port": 443})

        cfg = {
            "credentials": {
                "username": "admin user",
                "password": "pa ss'word",
                "panel_port": 9453,
            },
            "defaults": {"sni": "www.microsoft.com"},
        }

        with patch.object(fleet, "ssh_script", fake_ssh_script):
            fleet.create_inbound("node1", 443, "New York", cfg)

        argv = shlex.split(captured["args"])
        self.assertEqual(argv, ["443", "New York", "9453", "admin user", "pa ss'word", "www.microsoft.com"])

    def test_generate_subscription_can_enable_ipv6_dns(self):
        cfg = {
            "defaults": {"sni": "www.microsoft.com", "fingerprint": "chrome", "dns": {"ipv6": True}},
            "nodes": [{"ssh_host": "h1", "emoji": "🇯🇵", "name": "Tokyo", "server": "1.2.3.4", "port": 443}],
        }
        node_details = {
            "h1": {
                "inbounds": [{
                    "protocol": "vless",
                    "uuid": "00000000-0000-0000-0000-000000000000",
                    "public_key": "pub",
                    "short_id": "sid",
                    "sni": "www.microsoft.com",
                }]
            }
        }

        yaml_text = fleet.generate_subscription(cfg, node_details)

        self.assertIn("  ipv6: true", yaml_text)

    def test_remote_inbound_script_only_deletes_matching_managed_vless_inbound(self):
        script = fleet.REMOTE_INBOUND_SCRIPT

        self.assertNotIn('if ib.get("protocol") == "vless":', script)
        self.assertIn('ib.get("remark") == remark', script)

    def test_remote_inbound_script_accepts_xray_public_key_label_variants(self):
        script = fleet.REMOTE_INBOUND_SCRIPT

        self.assertIn('kv.get("Password")', script)
        self.assertIn('kv.get("Password (PublicKey)")', script)
        self.assertIn('kv.get("Public key", "")', script)

    def test_remote_scripts_try_https_panel_before_http_fallback(self):
        for script in (fleet.REMOTE_INBOUND_SCRIPT, fleet.REMOTE_QUERY_SCRIPT):
            self.assertIn("ssl", script)
            self.assertIn('for scheme in ("https", "http"):', script)
            self.assertIn("ssl._create_unverified_context()", script)
            self.assertIn("urllib.request.HTTPSHandler(context=ctx)", script)

    def test_remote_query_script_reports_errors_instead_of_silently_swallowing_them(self):
        script = fleet.REMOTE_QUERY_SCRIPT

        self.assertIn("except Exception as e:", script)
        self.assertIn("error = str(e)", script)
        self.assertIn('"error": error', script)
        self.assertNotIn("pass\n", script[script.index("except Exception as e:"):])

    def test_generate_subscription_yaml_contains_one_node(self):
        cfg = {
            "defaults": {"sni": "www.microsoft.com", "fingerprint": "chrome", "dns": {}},
            "nodes": [{"ssh_host": "h1", "emoji": "🇯🇵", "name": "Tokyo", "server": "1.2.3.4", "port": 443}],
        }
        node_details = {
            "h1": {
                "inbounds": [{
                    "protocol": "vless",
                    "uuid": "00000000-0000-0000-0000-000000000000",
                    "public_key": "pub",
                    "short_id": "sid",
                    "sni": "www.microsoft.com",
                }]
            }
        }

        yaml_text = fleet.generate_subscription(cfg, node_details)

        self.assertIn("type: vless", yaml_text)
        self.assertIn("🇯🇵 Tokyo", yaml_text)


if __name__ == "__main__":
    unittest.main()
