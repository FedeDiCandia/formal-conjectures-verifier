"""Il controllo di awake: niente giro se il Mac puo' sospendersi.

Nella notte del 13 settembre il Mac e' andato in sospensione durante il giro e
ogni sospensione ha chiuso one connessione con l'API. I testi qui below sono
presi da `pmset` su questa macchina, quella notte.
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


def test_riconosce_la_fonte_di_alimentazione():
    assert awake.power_source(POWER_AC) == "mains"
    assert awake.power_source(POWER_BATTERY) == "battery"
    assert awake.power_source("") == "unknown"


def test_riconosce_il_proprio_caffeinate_e_non_quello_di_altri():
    assert awake.caffeinate_running(ASSERTIONS, 96678)
    assert not awake.caffeinate_running(ASSERTIONS, 12345), "un other caffeinate non basta"
    assert not awake.caffeinate_running(ASSERTIONS, 340), "powerd non e' caffeinate"
    assert not awake.caffeinate_running(ASSERTIONS, None)


def test_a_batteria_non_si_parte_e_il_motivo_e_chiaro():
    reasons = awake.problems(POWER_BATTERY, ASSERTIONS, 96678)
    assert len(reasons) == 1 and "not plugged in" in reasons[0], reasons


def test_senza_caffeinate_non_si_parte():
    reasons = awake.problems(POWER_AC, "", 96678)
    assert len(reasons) == 1 and "caffeinate" in reasons[0], reasons


def test_con_alimentatore_e_caffeinate_si_parte():
    assert awake.problems(POWER_AC, ASSERTIONS, 96678) == []
