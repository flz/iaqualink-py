from dataclasses import dataclass
from typing import Any

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class ExoAux(DataClassJSONMixin):
    mode: int
    type: str
    color: int
    state: int


@dataclass
class ExoSensorData(DataClassJSONMixin):
    state: int
    value: int
    sensor_type: str


@dataclass
class ExoFilterPumpData(DataClassJSONMixin):
    type: int
    state: int


@dataclass
class ExoVspSpeed(DataClassJSONMixin):
    min: int
    max: int


@dataclass
class ExoSwcDevice(DataClassJSONMixin):
    """Represents the swc_0 equipment block in the shadow response.

    ``__pre_deserialize__`` collects the variable-key ``aux_*`` and ``sns_*``
    entries into typed dicts so that the rest of the fields can be declared
    as fixed dataclass members.
    """

    filter_pump: ExoFilterPumpData
    aux_devices: dict[str, ExoAux]
    sensors: dict[str, ExoSensorData]
    swc: int
    low: int
    vsp: int
    amp: int
    temp: int
    lang: int
    ph_sp: int
    boost: int
    orp_sp: int
    ph_only: int
    swc_low: int
    exo_state: int
    dual_link: int
    production: int
    error_code: int
    error_state: int
    aux230: int
    vsp_speed: ExoVspSpeed | None = None

    @classmethod
    def __pre_deserialize__(cls, d: dict[str, Any]) -> dict[str, Any]:
        d = dict(d)
        aux_devices: dict[str, Any] = {}
        sensors: dict[str, Any] = {}
        for key in list(d):
            if key.startswith("aux_"):
                aux_devices[key] = d.pop(key)
            elif key.startswith("sns_"):
                sensors[key] = d.pop(key)
        d["aux_devices"] = aux_devices
        d["sensors"] = sensors
        return d


@dataclass
class ExoHeating(DataClassJSONMixin):
    state: int
    sp: int
    enabled: int
    sp_min: int
    sp_max: int
    vsp_rpm_list: dict[str, int] | None = None
    vsp_rpm_index: int | None = None
    priority_enabled: int | None = None


@dataclass
class ExoShadowReported(DataClassJSONMixin):
    equipment: dict[str, ExoSwcDevice]
    heating: ExoHeating | None = None


@dataclass
class ExoShadowState(DataClassJSONMixin):
    reported: ExoShadowReported


@dataclass
class ExoShadowResponse(DataClassJSONMixin):
    state: ExoShadowState
