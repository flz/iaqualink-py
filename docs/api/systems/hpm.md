# HPM Systems API

HPM systems are standalone heat-pump-only devices using the zodiac-io.com API with the same AWS IoT-style shadow REST mechanism as `exo`.

## HpmSystem

::: iaqualink.systems.hpm.system.HpmSystem

## HpmDevice

::: iaqualink.systems.hpm.device.HpmDevice

## HpmHeatPump

::: iaqualink.systems.hpm.device.HpmHeatPump

## HpmMode

::: iaqualink.systems.hpm.device.HpmMode

## HpmCoolingPriority

::: iaqualink.systems.hpm.device.HpmCoolingPriority

## HpmOperatingStatusSensor

::: iaqualink.systems.hpm.device.HpmOperatingStatusSensor

## HpmStandbyReasonSensor

::: iaqualink.systems.hpm.device.HpmStandbyReasonSensor

## HpmProbeSensor

::: iaqualink.systems.hpm.device.HpmProbeSensor

## HpmWaterFlow

::: iaqualink.systems.hpm.device.HpmWaterFlow

## Usage Example

```python
from iaqualink import AqualinkClient
from iaqualink.system import SystemStatus

async with AqualinkClient(username, password) as client:
    systems = await client.get_systems()

    # Find HPM system
    for system in systems.values():
        if system.data.get('device_type') == 'hpm':
            await system.refresh()

            if system.status is SystemStatus.CONNECTED:
                devices = await system.get_devices()

                heatpump = devices['heatpump']
                print(f"On: {heatpump.is_on}, target: {heatpump.target_temperature}")

                await heatpump.turn_on()
                await heatpump.set_temperature(30)
```

## See Also

- [Implementation Notes](../../implementation/systems/hpm.md)
- [Protocol Reference](../../reference/systems/hpm.md)
