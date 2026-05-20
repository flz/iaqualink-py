from __future__ import annotations

import unittest

from iaqualink.utils.redact import redact_value


class TestRedactValue(unittest.TestCase):
    def test_scalar_str_passthrough(self) -> None:
        assert redact_value("hello") == "hello"

    def test_scalar_int_passthrough(self) -> None:
        assert redact_value(42) == 42

    def test_none_passthrough(self) -> None:
        assert redact_value(None) is None

    def test_dict_delegated_to_redact_dict(self) -> None:
        result = redact_value({"password": "secret", "command": "get_home"})
        assert result["password"] == "***"
        assert result["command"] == "get_home"

    def test_list_of_dicts_redacted(self) -> None:
        data = [
            {"serial_number": "TESTSERIAL1", "device_type": "iaqua"},
            {"serial_number": "TESTDEVICE2", "device_type": "i2d"},
        ]
        result = redact_value(data)
        assert isinstance(result, list)
        assert result[0]["serial_number"] == "***AL1"
        assert result[0]["device_type"] == "iaqua"
        assert result[1]["serial_number"] == "***CE2"

    def test_empty_list(self) -> None:
        assert redact_value([]) == []

    def test_list_of_scalars_passthrough(self) -> None:
        assert redact_value([1, 2, 3]) == [1, 2, 3]

    def test_nested_list_in_dict(self) -> None:
        data = {
            "systems": [
                {"serial_number": "TESTSERIAL1"},
                {"serial_number": "TESTDEVICE2"},
            ],
            "count": 2,
        }
        result = redact_value(data)
        assert result["systems"][0]["serial_number"] == "***AL1"
        assert result["systems"][1]["serial_number"] == "***CE2"
        assert result["count"] == 2

    def test_list_of_mixed_values(self) -> None:
        result = redact_value([{"password": "s"}, 42, "plain"])
        assert result[0]["password"] == "***"
        assert result[1] == 42
        assert result[2] == "plain"
