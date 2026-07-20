# TCX Systems API

TCX filtration and spa controllers communicate via AWS IoT Device Shadow. Reads are primarily WebSocket (`prod-socket.zodiac-io.com`), with REST shadow endpoints (`prod.zodiac-io.com`) as a one-shot bootstrap/fallback; writes are WebSocket `StateController` command frames.

## TcxSystem

::: iaqualink.systems.tcx.system.TcxSystem

## TcxDevice

::: iaqualink.systems.tcx.device.TcxDevice

## Device Classes

::: iaqualink.systems.tcx.device.TcxWaterSensor

::: iaqualink.systems.tcx.device.TcxAirSensor

::: iaqualink.systems.tcx.device.TcxSolarSensor

::: iaqualink.systems.tcx.device.TcxFilterPump

::: iaqualink.systems.tcx.device.TcxVariableSpeedPump

::: iaqualink.systems.tcx.device.TcxAuxSwitch

::: iaqualink.systems.tcx.device.TcxClimate

::: iaqualink.systems.tcx.device.TcxChlorinatorBoost
