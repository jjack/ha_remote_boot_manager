"""Constants for remote_boot_manager."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "remote_boot_manager"

DEFAULT_OS_NONE = "(none)"

WEBHOOK_ID = "remote_boot_manager_ingest"
WEBHOOK_NAME = "Remote Boot Manager Ingest"

BOOTLOADER_VIEW_URL = "/api/remote_boot_manager/{mac_address}"
