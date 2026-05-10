import json
import logging
from typing import Any, TypeVar

from mashumaro.codecs.json import JSONDecoder
from mashumaro.exceptions import (
    InvalidFieldValue,
    MissingField,
    SuitableVariantNotFoundError,
)
from mashumaro.mixins.json import DataClassJSONMixin

from .exception import AqualinkUnexpectedResponseException

LOGGER = logging.getLogger("iaqualink")

_MASHUMARO_ERRORS = (
    json.JSONDecodeError,
    MissingField,
    InvalidFieldValue,
    SuitableVariantNotFoundError,
)

_T = TypeVar("_T", bound=DataClassJSONMixin)


def json_to_dataclass(cls: type[_T], json_str: str) -> _T:
    try:
        return cls.from_json(json_str)
    except _MASHUMARO_ERRORS as e:
        LOGGER.error("Failed to parse JSON into %s: %s", cls.__name__, e)
        raise AqualinkUnexpectedResponseException(
            f"Error parsing JSON: {e}"
        ) from e


def decode_json(decoder: JSONDecoder[Any], json_str: str) -> Any:
    try:
        return decoder.decode(json_str)
    except _MASHUMARO_ERRORS as e:
        LOGGER.error("Failed to decode JSON response: %s", e)
        raise AqualinkUnexpectedResponseException(
            f"Error parsing JSON: {e}"
        ) from e
