"""Il log dell'agent: le lines devono arrivare sul file mentre gira.

Serve a one cosa sola, e non e' tecnica: chi guarda da un other terminale deve
poter vedere che il job sta andando. Prima il report si scriveva only alla
end, e un giro da un'now sembrava fermo.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "verifier"))

import agent


def test_scrive_su_schermo_e_su_file_riga_per_riga(tmp_path, capsys):
    log = tmp_path / "below" / "log.log"
    doppio = agent._Doppio(sys.stdout, log)
    doppio.write("before line\n")
    # la line deve essere GIA' sul file, senza aspettare la closure
    assert log.read_text(encoding="utf-8") == "before line\n"
    doppio.write("seconda line\n")
    assert log.read_text(encoding="utf-8").count("\n") == 2
    doppio.flush()
    assert "before line" in capsys.readouterr().out


def test_crea_la_cartella_se_manca(tmp_path):
    log = tmp_path / "a" / "b" / "c.log"
    agent._Doppio(sys.stdout, log).write("x\n")
    assert log.is_file()


def test_non_si_rompe_se_qualcuno_chiede_isatty(tmp_path):
    d = agent._Doppio(sys.stdout, tmp_path / "r.log")
    assert d.isatty() in (True, False)
