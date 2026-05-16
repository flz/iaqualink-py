# Home Assistant

The primary way most users interact with iaqualink-py is through the built-in Home Assistant integration.

## Built-in Integration

iaqualink-py is included in Home Assistant core as the `iaqualink` integration. No separate installation is required if you are running Home Assistant.

**Integration source:** [homeassistant/components/iaqualink](https://github.com/home-assistant/core/tree/dev/homeassistant/components/iaqualink)

## Setting Up in Home Assistant

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **iAqualink**
3. Enter your Jandy iAqualink account credentials (the same login you use for the iAqualink mobile app)
4. Home Assistant will discover your pool systems and add their devices automatically

## Supported Systems

| System type | Description |
|---|---|
| iAqua (`iaqua`) | Original Jandy iAqualink pool/spa controllers (IQ20 / IQ900) |
| eXO (`exo`) | Zodiac EXO salt water chlorinators |
| iQPump (`i2d`) | Jandy iQPump variable-speed pump controllers |

## Supported Devices

Device availability depends on your system type and hardware configuration. Common entities include:

- Pool and spa temperature sensors
- Air temperature sensor
- Thermostats (pool/spa set points)
- Pump and heater switches
- Lights
- Auxiliary switches
- Water chemistry sensors (pH, ORP, salinity — eXO)
- Variable speed pump control (i2d)

## Troubleshooting

If your system is not discovered or devices are missing, check:

- Your iAqualink app credentials work in the official mobile app
- Your pool controller is online and reachable
- The Home Assistant integration logs for errors (enable debug logging if needed)

For bugs in the HA integration itself, file issues against [home-assistant/core](https://github.com/home-assistant/core).
For bugs in this library, file issues against [flz/iaqualink-py](https://github.com/flz/iaqualink-py).

## Programmatic Use

If you want to use iaqualink-py directly from Python (outside of Home Assistant), see [Programmatic Use](quickstart.md).
