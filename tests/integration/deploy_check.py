#!/usr/bin/env python3
# See LICENSE file for licensing details.

"""Deploy the packed charm onto an ubuntu unit and check that the client installs.

The charm cannot register without a Landscape server, so this does not wait for
active status. It checks that no unit is in error and that the client package was
installed.

Set LANDSCAPE_CLIENT_CHARM_PATH to use a prebuilt charm. Otherwise the charm is
packed for LANDSCAPE_CLIENT_CHARM_INTEGRATION_PLATFORM (default ubuntu@24.04:amd64).
"""

import logging
import os
from pathlib import Path
import subprocess
import zipfile

import jubilant
import yaml

logging.basicConfig(level=logging.INFO)

METADATA = yaml.safe_load(Path("metadata.yaml").read_text())
APP_NAME = METADATA["name"]
WAIT_TIMEOUT_SECONDS = 60 * 20


def pack_charm(platform: str) -> Path:
    """Pack the charm for a single platform, since packing every platform is slow."""
    subprocess.run(["charmcraft", "pack", "--platform", platform], check=True)
    # Packed files are named like landscape-client_ubuntu@24.04-amd64.charm
    return Path(f"{APP_NAME}_{platform.replace(':', '-')}.charm").resolve()


def charm_base(charm: Path) -> str:
    """Return the base (for example ubuntu@24.04) that a packed charm was built for."""
    with zipfile.ZipFile(charm) as package:
        manifest = yaml.safe_load(package.read("manifest.yaml"))
    base = manifest["bases"][0]
    return f"{base['name']}@{base['channel']}"


def subordinate_is_present(status: jubilant.Status) -> bool:
    unit = status.apps["ubuntu"].units.get("ubuntu/0")
    return bool(unit and unit.subordinates)


def main() -> None:
    if charm_path := os.environ.get("LANDSCAPE_CLIENT_CHARM_PATH"):
        charm = Path(charm_path).resolve()
    else:
        platform = os.environ.get(
            "LANDSCAPE_CLIENT_CHARM_INTEGRATION_PLATFORM", "ubuntu@24.04:amd64"
        )
        charm = pack_charm(platform)

    with jubilant.temp_model() as juju:
        # A subordinate can only relate to a principal on a base the charm supports
        juju.deploy("ubuntu", base=charm_base(charm))
        juju.deploy(charm, APP_NAME)
        juju.integrate(APP_NAME, "ubuntu")

        # Blocked is expected without registration, so only errors fail the wait
        juju.wait(
            lambda status: subordinate_is_present(status) and jubilant.all_agents_idle(status),
            error=jubilant.any_error,
            timeout=WAIT_TIMEOUT_SECONDS,
        )

        # Raises TaskError if the package is not installed
        juju.exec("dpkg-query -W landscape-client", unit=f"{APP_NAME}/0")

    print("OK: charm deployed and landscape-client is installed")


if __name__ == "__main__":
    main()
