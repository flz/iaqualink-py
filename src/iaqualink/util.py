import logging

from mashumaro.exceptions import (
    InvalidFieldValue,
    MissingField,
    SuitableVariantNotFoundError,
)

from .exception import AqualinkUnexpectedResponseException

LOGGER = logging.getLogger("iaqualink")

_MASHUMARO_ERRORS = (
    MissingField,
    InvalidFieldValue,
    SuitableVariantNotFoundError,
)


def json_to_dataclass(cls, json_str: str):
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
