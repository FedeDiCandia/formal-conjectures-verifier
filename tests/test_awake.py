"""The keep-awake check: no run if the Mac can go to sleep.

On the night of 13 September the Mac slept during the run, and every sleep closed a
connection to the API. The texts below are taken from `pmset` on this machine, that
night.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

import awake

POWER_BATTERY = """Now drawing from 'Battery Power'
 -InternalBattery-0 (id=22282339)	100%; discharging; 3:23 remaining present: true
"""
POWER_AC = """Now drawing from 'AC Power'
 -InternalBattery-0 (id=22282339)	100%; charged; 0:00 remaining present: true
"""
ASSERTIONS = """   pid 96678(caffeinate): [0x00004d5200019da6] 00:00:04 PreventUserIdleSystemSleep named: "caffeinate command-line tool"
	Details: caffeinate asserting on behalf of Process ID 81497
   pid 340(powerd): [0x00004c2500019cfb] 00:04:06 PreventUserIdleSystemSleep named: "Powerd - Prevent sleep while display is on"
"""


def test_it_recognises_the_power_source():
    assert awake.power_source(POWER_AC) == "mains"
    assert awake.power_source(POWER_BATTERY) == "battery"
    assert awake.power_source("") == "unknown"


def test_it_recognises_its_own_caffeinate_and_not_other_peoples():
    assert awake.caffeinate_running(ASSERTIONS, 96678)
    assert not awake.caffeinate_running(ASSERTIONS, 12345), "another caffeinate is not enough"
    assert not awake.caffeinate_running(ASSERTIONS, 340), "powerd is not caffeinate"
    assert not awake.caffeinate_running(ASSERTIONS, None)


def test_on_battery_it_does_not_start_and_the_reason_is_clear():
    reasons = awake.problems(POWER_BATTERY, ASSERTIONS, 96678)
    assert len(reasons) == 1 and "not plugged in" in reasons[0], reasons


def test_without_caffeinate_it_does_not_start():
    reasons = awake.problems(POWER_AC, "", 96678)
    assert len(reasons) == 1 and "caffeinate" in reasons[0], reasons


def test_with_mains_power_and_caffeinate_it_starts():
    assert awake.problems(POWER_AC, ASSERTIONS, 96678) == []
