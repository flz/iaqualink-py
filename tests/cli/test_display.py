from __future__ import annotations

from iaqualink.device import AqualinkDevice

import iaqualink.cli.app as cli_module

from .conftest import (
    make_binary_sensor,
    make_climate,
    make_fan,
    make_light,
    make_number,
    make_sensor,
    make_switch,
)


def test_group_devices_all_types() -> None:
    devices = [
        ("t1", make_climate("Heater")),
        ("l1", make_light("Light")),
        ("s1", make_switch("Switch")),
        ("p1", make_fan("Pump")),
        ("nb1", make_number("RPM")),
        ("b1", make_binary_sensor("Freeze")),
        ("n1", make_sensor("Temp")),
    ]
    groups = cli_module._group_devices(devices)
    assert [label for _, label, _ in groups] == [
        "Climate",
        "Lights",
        "Switches",
        "Fans",
        "Numbers",
        "Sensors",
    ]
    sensors_group = next(g for g in groups if g[1] == "Sensors")
    assert len(sensors_group[2]) == 2


def test_group_devices_climate_not_swallowed_by_switch() -> None:
    climate = make_climate("Heater")
    groups = cli_module._group_devices([("h", climate)])
    assert len(groups) == 1
    assert groups[0][1] == "Climate"


def test_group_devices_light_not_swallowed_by_switch() -> None:
    light = make_light("Spa Light")
    groups = cli_module._group_devices([("l", light)])
    assert len(groups) == 1
    assert groups[0][1] == "Lights"


def test_group_devices_fan_grouped_as_fan() -> None:
    fan = make_fan("Filter Pump")
    groups = cli_module._group_devices([("p", fan)])
    assert len(groups) == 1
    assert groups[0][1] == "Fans"


def test_group_devices_number_grouped_as_number() -> None:
    number = make_number("RPM")
    groups = cli_module._group_devices([("nb", number)])
    assert len(groups) == 1
    assert groups[0][1] == "Numbers"


def test_group_devices_binary_sensor_in_sensors_group() -> None:
    binary = make_binary_sensor("Freeze")
    groups = cli_module._group_devices([("b", binary)])
    assert len(groups) == 1
    assert groups[0][1] == "Sensors"


def test_group_devices_unknown_type_goes_to_other() -> None:
    class _Unknown(AqualinkDevice):
        @property
        def label(self) -> str:
            return "X"

        @property
        def name(self) -> str:
            return "X"

        @property
        def manufacturer(self) -> str:
            return ""

        @property
        def model(self) -> str:
            return ""

    device = object.__new__(_Unknown)
    groups = cli_module._group_devices([("x", device)])
    assert len(groups) == 1
    assert groups[0][1] == "Other"


def test_group_devices_empty() -> None:
    assert cli_module._group_devices([]) == []
