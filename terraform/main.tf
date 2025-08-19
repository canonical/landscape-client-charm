# © 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "landscape_client" {
  name  = var.app_name
  model = var.model

  charm {
    name     = "landscape-client"
    channel  = var.channel
    revision = var.revision
    base     = var.base
  }

  config      = var.config
  # subordinate charms must be deployed without constraints
  units       = var.units
  trust       = true
}
