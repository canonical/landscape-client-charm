# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing
import base64
import os
import tempfile
import unittest
from unittest import mock

import charm
from charm import LandscapeClientCharm, CLIENT_CONFIG_CMD
from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Harness

from charms.operator_libs_linux.v0 import apt


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(LandscapeClientCharm)
        self.addCleanup(self.harness.cleanup)

        self.process_mock = mock.patch("charm.process_helper").start()
        self.apt_mock = mock.patch("charm.apt.add_package").start()
        self.from_installed_package_mock = mock.patch(
            "charm.apt.DebianPackage.from_installed_package"
        ).start()
        self.open_mock = mock.patch("builtins.open").start()
        self.open_mock.side_effect = mock.mock_open(read_data="[client]")

    def test_install(self):
        self.harness.begin_with_initial_hooks()
        self.apt_mock.assert_called_once_with("landscape-client")

    def test_install_error(self):
        self.apt_mock.side_effect = Exception
        self.from_installed_package_mock.side_effect = apt.PackageNotFoundError
        self.harness.begin_with_initial_hooks()
        self.harness.update_config()
        status = self.harness.charm.unit.status
        self.assertEqual(status.message, "Failed to install client!")
        self.assertIsInstance(status, BlockedStatus)

    @mock.patch("charm.update_config")
    @mock.patch("charm.LandscapeClientCharm.is_registered", return_value=False)
    def test_run(self, is_registered_mock, update_config_mock):
        """Test args get passed correctly to landscape-config and registers"""
        self.harness.begin()
        self.harness.update_config({"computer-title": "hello1"})
        self.assertIn(
            ("computer-title", "hello1"), update_config_mock.call_args.args[0].items()
        )
        self.process_mock.assert_called_once_with([CLIENT_CONFIG_CMD, "--silent"])
        status = self.harness.charm.unit.status
        self.assertEqual(status.message, "Client registered!")
        self.assertIsInstance(status, ActiveStatus)

    @mock.patch("charm.LandscapeClientCharm.is_registered", return_value=True)
    def test_restart_if_registered(self, is_registered_mock):
        """Restart client if it's registered"""
        self.harness.begin()
        self.harness.update_config({})
        self.process_mock.assert_called_once_with(
            ["systemctl", "restart", "landscape-client"]
        )

    def test_ppa_added(self):
        self.harness.begin()
        self.harness.update_config({"ppa": "ppa"})
        self.process_mock.assert_any_call(["add-apt-repository", "-y", "ppa"])

    def test_ppa_error(self):
        self.harness.begin()
        self.process_mock.return_value = False
        self.harness.update_config({"ppa": "ppa"})
        status = self.harness.charm.unit.status
        self.assertEqual(status.message, "Failed to add PPA!")
        self.assertIsInstance(status, BlockedStatus)

    @mock.patch("charm.update_config")
    def test_ppa_not_in_args(self, update_config_mock):
        """Test that the ppa arg does not end up in the landscape config"""
        self.harness.begin()
        self.harness.update_config({"ppa": "testppa"})
        self.assertNotIn("ppa", update_config_mock.call_args.args[0])

    @mock.patch("charm.update_config")
    def test_ssl_cert(self, update_config_mock):
        """Test that the base64 encoded ssl cert gets written successfully"""

        self.harness.begin()

        data = b"hello"

        data_b64 = "base64:" + base64.b64encode(data).decode()
        self.harness.update_config({"ssl-public-key": data_b64})

        self.open_mock().write.assert_called_once_with(data)

    def test_ssl_cert_invalid_file(self):
        self.harness.begin()
        self.harness.update_config({"ssl-public-key": "/path/to/nowhere"})
        status = self.harness.charm.unit.status
        self.assertEqual(status.message, "Certificate does not exist!")
        self.assertIsInstance(status, BlockedStatus)

    def test_relation_broken(self):
        self.harness.begin()
        rel_id = self.harness.add_relation("container", "ubuntu")
        self.harness.add_relation_unit(rel_id, "ubuntu/0")
        self.harness.remove_relation_unit(rel_id, "ubuntu/0")
        self.process_mock.assert_called_once_with(
            [CLIENT_CONFIG_CMD, "--silent", "--disable"]
        )

    def test_action_upgrade(self):
        self.harness.begin()
        self.harness.charm.unit.status = ActiveStatus("Active")
        event = mock.Mock()
        with mock.patch("charm.apt") as apt_mock:
            pkg_mock = mock.Mock()
            apt_mock.DebianPackage.from_apt_cache.return_value = pkg_mock
            self.harness.charm._upgrade(event)

        self.assertEqual(apt_mock.DebianPackage.from_apt_cache.call_count, 1)
        self.assertEqual(pkg_mock.ensure.call_count, 1)

    def test_action_register(self):
        self.harness.begin()
        self.harness.charm.unit.status = ActiveStatus("Active")
        event = mock.Mock()
        self.harness.charm._register(event)
        self.process_mock.assert_called_once_with([CLIENT_CONFIG_CMD, "--silent"])

    @mock.patch("charm.os")
    def test_disable_unattended_upgrades(self, remove_mock):
        """apt configuration is changed to disable unattended-upgrades if this
        config is `True`. If the config is changed again to `False`, the
        config override is deleted.
        """

        self.harness.begin()
        self.harness.charm.add_ppa = mock.Mock()
        self.harness.charm.run_landscape_client = mock.Mock()
        self.harness.update_config({"disable-unattended-upgrades": True})

        self.open_mock.assert_called_once_with(charm.APT_CONF_OVERRIDE, "w")

        self.harness.update_config({"disable-unattended-upgrades": False})

        remove_mock.remove.assert_called_once_with(charm.APT_CONF_OVERRIDE)

    def test_update_config(self):
        """
        Test that update config can write new values, remove unsetted settings
        and handle empty setting like proxy to override for local override
        """
        file_content = ("[client]"
                        "account_name = onward"
                        "https_proxy = http://10.123.46.78:3128")
        self.open_mock.side_effect = mock.mock_open(
            read_data=file_content
        )
        self.harness.begin()
        self.harness.update_config({
                                    "ping-url": "url",
                                    "account-name": "onward",
                                    "http-proxy": "",
                                   })
        text = "".join([call.args[0] for call in self.open_mock().write.mock_calls])
        # existing value
        self.assertIn("account_name = onward", text)
        # new value
        self.assertIn("ping_url = url", text)
        # empty value
        self.assertIn("http_proxy = \n", text)
        # unset value
        self.assertNotIn("https_proxy =", text)
