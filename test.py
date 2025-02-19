#! /usr/bin/env python3

import os

from yaml import dump, load

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader  # type: ignore

from iaqualink.client import AqualinkClient
from iaqualink.exception import AqualinkException


async def main():
    with open(os.path.expanduser("~/.config/iaqualink.yaml")) as f:
        config = load(f, Loader=Loader)

    data = {}

    async with AqualinkClient(
        username=config["username"], password=config["password"]
    ) as client:
        systems = await client.get_systems()
        for system, system_obj in systems.items():
            data[system] = system_obj.data
            try:
                devices = await system_obj.get_devices()
            except AqualinkException:
                pass
            else:
                data[system]["devices"] = devices

    print(dump(data, Dumper=Dumper, default_flow_style=False))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
