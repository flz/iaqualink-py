from serde import SerdeError
from serde.json import from_json

from .exception import AqualinkException


def json_to_dataclass(cls, json_str: str):
    try:
        res = from_json(cls, json_str)
    except SerdeError as e:
        print(json_str)
        print(e)
        raise AqualinkException(f"Error parsing JSON: {e}") from e
    else:
        return res
