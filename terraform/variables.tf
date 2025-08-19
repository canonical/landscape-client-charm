# © 2025 Canonical Ltd.
# See LICENSE file for licensing details.

variable "app_name" {
  description = "Name of the application in the Juju model."
  type        = string
  default     = "landscape-client"
}

variable "base" {
  description = "The operating system on which to deploy"
  type        = string
  default     = "ubuntu@24.04"
}

variable "channel" {
  description = "The channel to use when deploying a charm."
  type        = string
  default     = "latest/edge"
}

variable "config" {
  description = "Application config. Details about available options can be found at https://charmhub.io/landscape-client/configurations?channel=latest/edge."
  type        = map(string)
  default     = {}
}

variable "model" {
  description = "Reference to a `juju_model`."
  type        = string
}

variable "revision" {
  description = "Revision number of the charm"
  type        = number
  # i.e., latest revision available for the channel
  default     = null
  nullable    = true
}

variable "units" {
  description = "Number of units to deploy"
  type        = number
  default     = 1
}
