#! /usr/bin/env python3

import os

import anyio
import yaml

from iaqualink.client import AqualinkClient
from iaqualink.exception import AqualinkException


async def main():
    async with await anyio.open_file(
        os.path.expanduser("~/.config/iaqualink.yaml")
    ) as f:
        config = yaml.safe_load(await f.read())

    data = {}

    async with AqualinkClient(
        username=config["username"], password=config["password"]
    ) as client:
        systems = await client.get_systems()
        for system, system_obj in systems.items():
            data[system] = {}
            data[system]["info"] = system_obj.data
            data[system]["devices"] = {}
            try:
                devices = await system_obj.get_devices()
            except AqualinkException:
                continue
            for device_name, device_data in devices.items():
                data[system]["devices"][device_name] = device_data.data

    print(yaml.dump(data, default_flow_style=False))  # noqa: T201


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
