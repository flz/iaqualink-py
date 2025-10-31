# iaqualink-py

> Asynchronous Python library for Jandy iAqualink pool control systems

[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)

## Overview

**iaqualink-py** is a modern, fully asynchronous Python library for interacting with Jandy iAqualink pool and spa control systems. It provides a clean, Pythonic interface to monitor and control your pool equipment from your Python applications.

## Features

- **Fully Asynchronous** - Built with `asyncio` and `httpx` for efficient, non-blocking I/O
- **Multi-System Support**
    - **iAqua** systems (iaqualink.net API)
    - **eXO** systems (zodiac-io.com API)
- **Comprehensive Device Support**
    - Temperature sensors (pool, spa, air)
    - Thermostats with adjustable set points
    - Pumps and heaters
    - Lights with toggle control
    - Auxiliary switches
    - Water chemistry sensors (pH, ORP, salinity)
    - Freeze protection monitoring
- **Context Manager Support** - Automatic resource cleanup
- **Type Safe** - Full type hints for modern Python development
- **Rate Limiting** - Built-in throttling to respect API limits

## Quick Example

```python
from iaqualink import AqualinkClient

async with AqualinkClient('user@example.com', 'password') as client:
    # Discover your pool systems
    systems = await client.get_systems()

    # Get the first system
    system = list(systems.values())[0]
    print(f"Found system: {system.name}")

    # Get all devices
    devices = await system.get_devices()

    # Access specific devices
    pool_temp = devices.get('pool_temp')
    if pool_temp:
        print(f"Pool temperature: {pool_temp.state}°F")

    # Control devices
    pool_pump = devices.get('pool_pump')
    if pool_pump:
        await pool_pump.turn_on()
```

## Requirements

- Python 3.13 or higher
- httpx with HTTP/2 support

## Next Steps

- [Installation](getting-started/installation.md) - Install the library
- [Quick Start](getting-started/quickstart.md) - Get started quickly
- [API Reference](api/client.md) - Detailed API documentation

## Disclaimer

This is an unofficial library and is not affiliated with or endorsed by Jandy, Zodiac Pool Systems, or Fluidra. Use at your own risk.
