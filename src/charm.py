#!/usr/bin/env python3
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

import base64
import logging
import os
import re
import subprocess
import traceback

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, BlockedStatus

from charms.operator_libs_linux.v0 import apt


logger = logging.getLogger(__name__)

CERT_FILE = "/etc/ssl/certs/landscape_server_ca.crt"
CLIENT_CONFIG_CMD = "/usr/bin/landscape-config"
CLIENT_PACKAGE = "landscape-client"

# These configs are not part of landscape client so we don't pass them to it
CHARM_ONLY_CONFIGS = ["ppa"]


class ClientCharmError(Exception):
    pass


def log_error(text, event=None):
    if text:  # Sometimes the subprocess output is empty
        logger.critical(text)
    if event:
        event.fail(text)


def log_info(text, event=None):
    text = "LANDSCAPE CLIENT CHARM INFO: {}".format(text)
    if text:  # Sometimes the subprocess output is empty
        logger.info(text)
    if event:
        event.log(text)


def write_certificate(certificate, filename):
    """
    @param certificate Text of the certificate, base64 encoded.
    @param filename Full path to file to write
    """
    with open(filename, "wb") as file:
        file.write(base64.b64decode(certificate))


def parse_ssl_arg(value):
    """
    If ssl config starts with 'base64' or is too long to be a file, decode
    and write it to the default cert path, return the default path. Else
    make sure the file exists and return the original value
    """
    b64_prefix = "base64:"
    if value.startswith(b64_prefix) or len(value) > 4096:
        value = re.sub("^" + b64_prefix, "", value)
        write_certificate(value, CERT_FILE)
        value = CERT_FILE
    else:
        if not os.path.isfile(value):
            log_error("Cert {} does not exist!".format(value))
            raise ClientCharmError("Certificate does not exist!")

    return value


def process_helper(args):
    """
    Grabs all outputs and exceptions from subprocess and look for
    keywords that indicate failure and return if successful or not
    """
    log_info(args)
    try:
        p = subprocess.Popen(
            args, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, text=True
        )
    except Exception:
        log_error(traceback.format_exc())
        return False
    output, error = p.communicate()
    if p.returncode != 0 or "Failure" in output:
        log_error("".join(traceback.format_stack()))
        log_error(output)
        log_error(error)
        return False
    else:
        log_info(output)
        return True


class LandscapeClientCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(
            self.on.mycontainer_relation_departed, self._on_relation_departed
        )
        self.framework.observe(self.on.upgrade_action, self._upgrade)
        self._stored.set_default(things=[])

    def add_ppa(self):
        landscape_ppa = self.config.get("ppa")
        if landscape_ppa:
            self.unit.status = MaintenanceStatus("Adding client PPA..")
            if not process_helper(["add-apt-repository", "-y", landscape_ppa]):
                raise ClientCharmError("Failed to add PPA!")

    def install_landscape_client(self):
        self.unit.status = MaintenanceStatus("Installing landscape client..")
        try:
            apt.add_package(CLIENT_PACKAGE)
        except Exception:
            log_error(traceback.format_exc())
            raise ClientCharmError("Failed to install client!")

    def parse_client_config_args(self):
        """
        Gets and processes the landscape client config args
        from the charm configuration
        """

        configs = []
        for key, value in self.config.items():

            if key in CHARM_ONLY_CONFIGS:
                continue
            if not value:
                continue

            if key == "ssl-public-key":
                value = parse_ssl_arg(value)

            # `Popen` can't handle non-string/bytes arguments.
            value = str(value)

            configs.append("--" + key)
            configs.append(value)

        return configs

    def run_landscape_client(self):
        self.unit.status = MaintenanceStatus("Configuring landscape client..")

        configs = self.parse_client_config_args()
        args = [CLIENT_CONFIG_CMD, "--silent"] + configs

        if process_helper(args):
            self.unit.status = ActiveStatus("Client registered!")
        else:
            raise ClientCharmError("Registration failed!")

    def _on_install(self, _):
        try:
            self.add_ppa()
            self.install_landscape_client()
        except ClientCharmError as exc:
            self.unit.status = BlockedStatus(str(exc))

    def _on_config_changed(self, _):
        try:
            apt.DebianPackage.from_installed_package(CLIENT_PACKAGE)
        except apt.PackageNotFoundError:
            log_error("Landscape client package not installed.")
            return
        try:
            self.add_ppa()
            self.run_landscape_client()
        except ClientCharmError as exc:
            self.unit.status = BlockedStatus(str(exc))

    def _on_relation_departed(self, _):
        """Disable landscape client when relation is broken"""
        self.unit.status = MaintenanceStatus("Disabling landscape client..")
        process_helper([CLIENT_CONFIG_CMD, "--silent", "--disable"])

    def _upgrade(self, event):

        if isinstance(self.unit.status, MaintenanceStatus):
            log_error("Please wait until charm is ready before upgrading.", event=event)
            return

        self.add_ppa()
        apt.update()

        try:
            log_info("Upgrading landcape client..", event=event)
            pkg = apt.DebianPackage.from_apt_cache(CLIENT_PACKAGE)
            pkg.ensure(state=apt.PackageState.Latest)
            installed = apt.DebianPackage.from_installed_package(CLIENT_PACKAGE)
            log_info("Upgraded to {}...".format(installed.version), event=event)
        except Exception as exc:
            log_error("Could not upgrade landscape client!", event=event)
            log_error(traceback.format_exc(), event=event)
            self.unit.status = BlockedStatus(str(exc))


if __name__ == "__main__":
    main(LandscapeClientCharm)
