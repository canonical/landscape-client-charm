# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing
import base64
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

    def test_install(self):
        self.harness.begin_with_initial_hooks()
        self.apt_mock.assert_called_once_with("landscape-client")

    @mock.patch("charm.apt.DebianPackage.from_installed_package")
    def test_install_error(self, from_installed_package_mock):
        self.apt_mock.side_effect = Exception
        from_installed_package_mock.side_effect = apt.PackageNotFoundError
        self.harness.begin_with_initial_hooks()
        self.harness.update_config()
        status = self.harness.charm.unit.status
        self.assertEqual(status.message, "Failed to install client!")
        self.assertIsInstance(status, BlockedStatus)

    def test_run(self):
        """Test args get passed correctly to landscape-config and no errors"""
        self.harness.begin()
        self.harness.update_config({"computer-title": "hello1"})
        args = [CLIENT_CONFIG_CMD, "--silent", "--computer-title", "hello1"]
        self.process_mock.assert_called_once_with(args)
        status = self.harness.charm.unit.status
        self.assertEqual(status.message, "Client registered!")
        self.assertIsInstance(status, ActiveStatus)

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

    def test_ppa_not_in_args(self):
        """Test that the ppa arg does not end up in the landscape config"""
        self.harness.begin()
        self.harness.update_config({"ppa": "testppa"})
        self.process_mock.assert_any_call([CLIENT_CONFIG_CMD, "--silent"])

    def test_ssl_cert(self):
        """Test that the base64 encoded ssl cert gets written successfully"""

        self.harness.begin()

        data = b"hello"

        with tempfile.NamedTemporaryFile() as tmp:

            charm.CERT_FILE = tmp.name

            data_b64 = "base64:" + base64.b64encode(data).decode()
            self.harness.update_config({"ssl-public-key": data_b64})

            self.assertEqual(tmp.read(), data)

    def test_ssl_cert_invalid_file(self):
        self.harness.begin()
        self.harness.update_config({"ssl-public-key": "/path/to/nowhere"})
        status = self.harness.charm.unit.status
        self.assertEqual(status.message, "Certificate does not exist!")
        self.assertIsInstance(status, BlockedStatus)

    def test_relation_broken(self):
        self.harness.begin()
        rel_id = self.harness.add_relation("mycontainer", "ubuntu")
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
