# Device Security for Home Assistant

Custom integration that sends your Home Assistant device registry to the platform and shows vulnerability findings back as sensors.

Home Assistant knows the exact manufacturer, model, firmware version and MAC address of the devices it controls, including Zigbee, Z-Wave, Matter and Thread devices behind a hub that no network scan can see. The platform matches that data against known vulnerabilities.

All traffic goes from Home Assistant to the platform. The platform never connects to Home Assistant and never holds a Home Assistant token.

## Install

1. HACS > Integrations > menu > Custom repositories: add this repository, category **Integration**.
2. Install **Device Security**, restart Home Assistant.
3. Settings > Devices & services > Add integration > **Device Security**.
4. Enter:
   - **API URL**, **Tenant** and **API token**: press **Connect Home Assistant** on the *API Keys & Integrations* tab of your account page and copy the values it shows.

## What is sent

Every 6 hours, on start-up and within a minute of a device registry change, `POST /api/v1/home-assistant/registry` with:

- Home Assistant instance id and version;
- this host's MAC and IPv4 addresses (so devices on a USB Zigbee stick or Thread border router can be placed under it);
- for each device registry entry: id, hub (`via_device_id`), integration domain, manufacturer, model, model id, firmware (`sw_version`), hardware version, name, your name for it, entry type, connections (MAC, Zigbee IEEE, Bluetooth) and the domains of its entities.

No states, history, entity names, locations or credentials are sent.

## Sensors

From `GET /api/v1/home-assistant/summary`, every 30 minutes:

| Sensor | Meaning |
| --- | --- |
| Devices with critical vulnerabilities | Devices whose worst open finding is critical |
| Devices with high vulnerabilities | Devices whose worst open finding is high |
| Devices at risk | Devices with any open finding; attribute `devices` lists the Home Assistant ones |
| Critical vulnerabilities | Open critical findings |
| High vulnerabilities | Open high findings |
| Vulnerabilities | All open findings |
| Linked devices (diagnostic) | Registry entries the platform matched to a device |
| Last device sync (diagnostic) | When the platform last applied the registry |

Example automation:

```yaml
automation:
  - alias: Notify on critical device vulnerabilities
    triggers:
      - trigger: numeric_state
        entity_id: sensor.device_security_demo_devices_with_critical_vulnerabilities
        above: 0
    actions:
      - action: notify.notify
        data:
          message: "Device Security: {{ trigger.to_state.state }} device(s) with critical vulnerabilities"
```

## Development

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

CI (`.github/workflows/validate.yml`) runs hassfest, HACS validation and the tests.
