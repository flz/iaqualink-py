from __future__ import annotations

import json
import unittest
from dataclasses import dataclass

import pytest
from mashumaro.codecs.json import JSONDecoder
from mashumaro.mixins.json import DataClassJSONMixin

from iaqualink.exception import AqualinkUnexpectedResponseException
from iaqualink.util import decode_json, json_to_dataclass


@dataclass
class _Simple(DataClassJSONMixin):
    value: int


class TestJsonToDataclass(unittest.TestCase):
    def test_valid_json_returns_dataclass(self) -> None:
        result = json_to_dataclass(_Simple, '{"value": 42}')
        assert result == _Simple(value=42)

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(AqualinkUnexpectedResponseException):
            json_to_dataclass(_Simple, "not json{{{")

    def test_wrong_schema_raises(self) -> None:
        with pytest.raises(AqualinkUnexpectedResponseException):
            json_to_dataclass(_Simple, '{"wrong_field": 1}')


class TestDecodeJson(unittest.TestCase):
    _decoder: JSONDecoder[list[_Simple]] = JSONDecoder(list[_Simple])

    def test_valid_json_returns_list(self) -> None:
        result = decode_json(self._decoder, '[{"value": 1}, {"value": 2}]')
        assert result == [_Simple(value=1), _Simple(value=2)]

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(AqualinkUnexpectedResponseException):
            decode_json(self._decoder, "not json{{{")

    def test_wrong_schema_raises(self) -> None:
        with pytest.raises(AqualinkUnexpectedResponseException):
            decode_json(self._decoder, json.dumps([{"wrong_field": 1}]))
