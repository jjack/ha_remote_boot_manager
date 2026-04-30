# Remote Boot Manager for Home Assistant

Manage and automate the booting of your remote bare-metal servers (like dual-boot Windows/Linux machines) directly from Home Assistant.

This integration works in tandem with the [Remote Boot Agent](https://github.com/jjack/remote-boot-agent) to automatically discover your servers, display their available Operating Systems, allow you to select which OS to boot into next, and wake them up via Wake-on-LAN.

## Features
* **Dynamic OS Discovery**: Servers automatically report their available OS list (e.g., Ubuntu, Windows) to Home Assistant.
* **Next Boot Selection**: Change the next boot OS via a dropdown `select` entity.
* **Wake-on-LAN**: Wake up sleeping servers and track their power state via a `switch` entity.
* **Drop-in Wake-on-LAN Replacement**: Exposes a `remote_boot_manager.send_magic_packet` service that can be used directly in automations, mimicking the official HA integration.
* **Bootloader Integration**: Exposes an endpoint for GRUB (or other bootloaders) to fetch the selected OS and automatically reset to prevent boot loops.
* **Secure Webhooks**: Uses auto-generated, secure webhooks for agent-to-HA communication.

## Installation

### Via HACS (Recommended)
1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Click the 3 dots in the top right -> **Custom repositories**.
4. Add `jjack/hass-remote-boot-manager` as an Integration.
5. Download it and restart Home Assistant.

### Manual Installation
1. Copy the `custom_components/remote_boot_manager` directory to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Configuration & Setup

1. Go to **Settings** -> **Devices & Services** in Home Assistant.
2. Click **+ Add Integration** and search for "Remote Boot Manager".
3. **IMPORTANT:** During setup, Home Assistant will generate a unique, secure `webhook_id`. **You must copy and save this ID and the example configuration!** It is only shown to you once for security reasons. You will need it to configure your remote servers.

## Remote Boot Agent (Client Setup)

For this integration to work, you must install a bare-metal GO agent on **every** target server you want to manage.

**Agent Repository:** [jjack/remote-boot-agent](https://github.com/jjack/remote-boot-agent)

### Basic Agent Setup:
1. Install the agent on your target server.
2. Configure the agent using your Home Assistant URL and the `webhook_id` you saved during the integration setup.
3. Run the agent. It will automatically ping Home Assistant, and your server will instantly appear as a new Device!

*(Full installation and configuration instructions for the agent are TBD and can be found at the [remote-boot-agent repository](https://github.com/jjack/remote-boot-agent)).*
