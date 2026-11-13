# See LICENSE file for licensing details.

"""Fixtures for deploying the packed charm with jubilant."""

import logging
import os
from pathlib import Path
import subprocess
import zipfile

import jubilant
import pytest
import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_NAME = yaml.safe_load((PROJECT_ROOT / "metadata.yaml").read_text())["name"]


def pack_charm(platform: str) -> Path:
    """Pack the charm for a single platform, since packing every platform is slow."""
    subprocess.run(["charmcraft", "pack", "--platform", platform], check=True, cwd=PROJECT_ROOT)
    # Packed files are named like landscape-client_ubuntu@24.04-amd64.charm
    return PROJECT_ROOT / f"{APP_NAME}_{platform.replace(':', '-')}.charm"


def charm_base(charm: Path) -> str:
    """Return the base (for example ubuntu@24.04) that a packed charm was built for."""
    with zipfile.ZipFile(charm) as package:
        manifest = yaml.safe_load(package.read("manifest.yaml"))
    base = manifest["bases"][0]
    return f"{base['name']}@{base['channel']}"


@pytest.fixture(scope="module")
def charm() -> Path:
    """Use LANDSCAPE_CLIENT_CHARM_PATH if set, otherwise pack the charm."""
    if charm_path := os.environ.get("LANDSCAPE_CLIENT_CHARM_PATH"):
        return Path(charm_path).resolve()
    platform = os.environ.get("LANDSCAPE_CLIENT_CHARM_INTEGRATION_PLATFORM", "ubuntu@24.04:amd64")
    return pack_charm(platform)


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest):
    """Provide a temporary model, dumping the debug log on failure."""
    with jubilant.temp_model() as juju:
        yield juju
        if request.session.testsfailed:
            logger.info(juju.debug_log(limit=1000))


@pytest.fixture(scope="module")
def deployed(juju: jubilant.Juju, charm: Path) -> jubilant.Juju:
    """Deploy the charm as a subordinate of ubuntu."""
    # A subordinate can only relate to a principal on a base the charm supports
    juju.deploy("ubuntu", base=charm_base(charm))
    juju.deploy(charm, APP_NAME)
    juju.integrate(APP_NAME, "ubuntu")
    return juju
