"""Constants for remote_boot_manager."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "remote_boot_manager"
DOMAIN_DATA = f"{DOMAIN}.servers"

DEFAULT_OS_NONE = "(none)"

WEBHOOK_ID = "remote_boot_manager_ingest"
WEBHOOK_NAME = "Remote Boot Manager Ingest"
WEBHOOK_MAX_PAYLOAD_BYTES = 102400  # 100 KB limit

BOOTLOADER_VIEW_URL = "/api/remote_boot_manager/{mac_address}"

SAVE_DELAY = 15.0  # seconds to debounce saving to storage after changes

SIGNAL_NEW_SERVER = f"{DOMAIN}_new_server"
