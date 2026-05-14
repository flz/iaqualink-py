from __future__ import annotations

import unittest

import pytest

from iaqualink.util import sign


class TestSign(unittest.IsolatedAsyncioTestCase):
    def test_single_part(self) -> None:
        assert sign(["foo"], "secret") == "9baed91be7f58b57c824b60da7cb262b2ecafbd2"

    def test_two_parts_joined_with_comma(self) -> None:
        assert sign(["foo", "bar"], "secret") == "f8a1d5f86b75816db3efe1e2f0ae961e721b5cb7"

    def test_three_parts(self) -> None:
        assert sign(["a", "b", "c"], "secret") == "86cbb34b4f6bf6e24b6524c2d5e6c6c9490a5615"

    def test_empty_parts_raises(self) -> None:
        with pytest.raises(ValueError):
            sign([], "secret")
