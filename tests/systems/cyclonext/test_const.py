from __future__ import annotations

import unittest

from iaqualink.systems.cyclonext import const


class TestCyclonextConst(unittest.TestCase):
    def test_mode_values(self) -> None:
        # Confirmed live during T16 against vendor mobile app.
        assert const.MODE_STOP == 0
        assert const.MODE_START == 1
        assert const.MODE_PAUSE == 2

    def test_mode_labels_cover_all_modes(self) -> None:
        assert set(const.MODE_LABELS) == {
            const.MODE_STOP,
            const.MODE_START,
            const.MODE_REMOTE,
            const.MODE_LIFT,
        }

    def test_pause_alias_equals_remote(self) -> None:
        # Live RE confirmed mode 2 is the Remote-control surface, not a
        # cycle pause; we keep MODE_PAUSE as a back-compat alias.
        assert const.MODE_PAUSE == const.MODE_REMOTE == 2

    def test_remote_direction_values(self) -> None:
        assert const.DIRECTION_FORWARD == 1
        assert const.DIRECTION_BACKWARD == 2
        assert const.DIRECTION_ROTATE_RIGHT == 3
        assert const.DIRECTION_ROTATE_LEFT == 4
        assert const.DIRECTION_STOP == 0

    def test_lift_direction_values(self) -> None:
        assert const.MODE_LIFT == 3
        assert const.DIRECTION_LIFT_EJECT == 5
        assert const.DIRECTION_LIFT_ROTATE_LEFT == 6
        assert const.DIRECTION_LIFT_ROTATE_RIGHT == 7

    def test_cycle_floor_maps_to_quick_tim(self) -> None:
        # Floor cycle (id=1) total observed = 90 min == durations.quickTim
        # on the captured shadow. Confirmed live 2026-04-27.
        assert const.CYCLE_FLOOR == 1
        assert const.CYCLE_DURATION_KEY[const.CYCLE_FLOOR] == "quickTim"

    def test_cycle_floor_and_walls_present(self) -> None:
        # Per galletn/iaqualink HA integration; pending live capture.
        assert const.CYCLE_FLOOR_AND_WALLS == 3
        assert (
            const.CYCLE_DURATION_KEY[const.CYCLE_FLOOR_AND_WALLS] == "deepTim"
        )

    def test_cycle_labels_known(self) -> None:
        assert const.CYCLE_LABELS[const.CYCLE_FLOOR] == "floor"
        assert (
            const.CYCLE_LABELS[const.CYCLE_FLOOR_AND_WALLS] == "floor_and_walls"
        )

    def test_duration_keys_complete(self) -> None:
        # Captured live from shadow on 2026-04-27.
        assert set(const.DURATION_KEYS) == {
            "customTim",
            "deepTim",
            "firstSmartTim",
            "quickTim",
            "scanTim",
            "smartTim",
            "waterTim",
        }
