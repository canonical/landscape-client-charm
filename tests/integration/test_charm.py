# See LICENSE file for licensing details.

"""Deploy the packed charm onto an ubuntu unit and check that the client installs.

The charm cannot register without a Landscape server, so this does not wait for
active status. It checks that no unit is in error and that the client package was
installed.
"""

from conftest import APP_NAME
import jubilant

WAIT_TIMEOUT_SECONDS = 60 * 20


def subordinate_is_present(status: jubilant.Status) -> bool:
    unit = status.apps["ubuntu"].units.get("ubuntu/0")
    return bool(unit and unit.subordinates)


def test_deploy_and_install(deployed: jubilant.Juju):
    # Blocked is expected without registration, so only errors fail the wait
    deployed.wait(
        lambda status: subordinate_is_present(status) and jubilant.all_agents_idle(status),
        error=jubilant.any_error,
        timeout=WAIT_TIMEOUT_SECONDS,
    )

    # Raises TaskError if the package is not installed
    deployed.exec("dpkg-query -W landscape-client", unit=f"{APP_NAME}/0")
