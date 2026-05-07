"""Constants for grub_os_selector."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

CONF_BOOT_OPTIONS = "boot_options"
CONF_TURN_OFF = "turn_off"

DEFAULT_NAME = "Grub OS Selector"

DOMAIN = "grub_os_selector"
DOMAIN_DATA = f"{DOMAIN}.hosts"

DEFAULT_BOOT_OPTION_NONE = "(none)"

WEBHOOK_NAME = "Grub OS Selector Ingest"
WEBHOOK_MAX_PAYLOAD_BYTES = 102400  # 100 KB limit

GRUB_OS_REPORTER_URL = "https://github.com/jjack/grub-os-reporter"
GRUB_VIEW_URL = "/api/grub_os_selector/{mac_address}"

SAVE_DELAY = 15.0  # seconds to debounce saving to storage after changes

SIGNAL_NEW_HOST = f"{DOMAIN}_new_host"

WAIT_FOR_HOST_POWER_SECONDS = 10

PING_COUNT = 1
PING_TIMEOUT_SECONDS = 1
