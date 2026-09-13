"""Il controllo di veglia: niente giro se il Mac puo' sospendersi.

Nella notte del 13 settembre il Mac e' andato in sospensione durante il giro e
ogni sospensione ha chiuso una connessione con l'API. I testi qui sotto sono
presi da `pmset` su questa macchina, quella notte.
"""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "agent"))

import veglia

BATT_BATTERIA = """Now drawing from 'Battery Power'
 -InternalBattery-0 (id=22282339)	100%; discharging; 3:23 remaining present: true
"""
BATT_ALIMENTATORE = """Now drawing from 'AC Power'
 -InternalBattery-0 (id=22282339)	100%; charged; 0:00 remaining present: true
"""
ASSERZIONI = """   pid 96678(caffeinate): [0x00004d5200019da6] 00:00:04 PreventUserIdleSystemSleep named: "caffeinate command-line tool"
	Details: caffeinate asserting on behalf of Process ID 81497
   pid 340(powerd): [0x00004c2500019cfb] 00:04:06 PreventUserIdleSystemSleep named: "Powerd - Prevent sleep while display is on"
"""


def test_riconosce_la_fonte_di_alimentazione():
    assert veglia.fonte_alimentazione(BATT_ALIMENTATORE) == "alimentatore"
    assert veglia.fonte_alimentazione(BATT_BATTERIA) == "batteria"
    assert veglia.fonte_alimentazione("") == "sconosciuta"


def test_riconosce_il_proprio_caffeinate_e_non_quello_di_altri():
    assert veglia.caffeinate_attivo(ASSERZIONI, 96678)
    assert not veglia.caffeinate_attivo(ASSERZIONI, 12345), "un altro caffeinate non basta"
    assert not veglia.caffeinate_attivo(ASSERZIONI, 340), "powerd non e' caffeinate"
    assert not veglia.caffeinate_attivo(ASSERZIONI, None)


def test_a_batteria_non_si_parte_e_il_motivo_e_chiaro():
    motivi = veglia.problemi(BATT_BATTERIA, ASSERZIONI, 96678)
    assert len(motivi) == 1 and "alimentatore" in motivi[0], motivi


def test_senza_caffeinate_non_si_parte():
    motivi = veglia.problemi(BATT_ALIMENTATORE, "", 96678)
    assert len(motivi) == 1 and "caffeinate" in motivi[0], motivi


def test_con_alimentatore_e_caffeinate_si_parte():
    assert veglia.problemi(BATT_ALIMENTATORE, ASSERZIONI, 96678) == []
