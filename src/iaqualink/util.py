import logging
from typing import TypeVar

from mashumaro.exceptions import (
    InvalidFieldValue,
    MissingField,
    SuitableVariantNotFoundError,
)
from mashumaro.mixins.json import DataClassJSONMixin

from .exception import AqualinkUnexpectedResponseException

LOGGER = logging.getLogger("iaqualink")

_MASHUMARO_ERRORS = (
    MissingField,
    InvalidFieldValue,
    SuitableVariantNotFoundError,
)

_T = TypeVar("_T", bound=DataClassJSONMixin)


def json_to_dataclass(cls: type[_T], json_str: str) -> _T:
    try:
        res = cls.from_json(json_str)
    except _MASHUMARO_ERRORS as e:
        LOGGER.error(
            "Failed to parse JSON into %s: %s\n%s", cls.__name__, e, json_str
        )
        raise AqualinkUnexpectedResponseException(
            f"Error parsing JSON: {e}"
        ) from e
    else:
        return res
