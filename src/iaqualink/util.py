import json
import logging
from typing import Any, Callable, TypeVar

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
_D = TypeVar("_D")


def _parse(operation: Callable[[], _D], label: str) -> _D:
    try:
        return operation()
    except _MASHUMARO_ERRORS as e:
        LOGGER.debug("Failed to parse JSON into %s: %s", label, e)
        raise AqualinkUnexpectedResponseException(
            f"Error parsing JSON: {e}"
        ) from e


def json_to_dataclass(cls: type[_T], json_str: str) -> _T:
    return _parse(lambda: cls.from_json(json_str), cls.__name__)


def decode_json(decoder: JSONDecoder[Any], json_str: str) -> Any:
    """Decode JSON via a pre-built JSONDecoder (use when target is not a DataClassJSONMixin)."""
    return _parse(lambda: decoder.decode(json_str), "response")
