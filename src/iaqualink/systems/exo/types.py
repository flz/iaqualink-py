from dataclasses import dataclass
from typing import Any

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class ExoHeating(DataClassJSONMixin):
    state: int
    sp: int
    enabled: int
    sp_min: int
    sp_max: int


@dataclass
class ExoShadowReported(DataClassJSONMixin):
    equipment: dict[str, Any]
    heating: ExoHeating | None = None


@dataclass
class ExoShadowState(DataClassJSONMixin):
    reported: ExoShadowReported


@dataclass
class ExoShadowResponse(DataClassJSONMixin):
    state: ExoShadowState
