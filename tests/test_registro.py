"""Il registro dell'agente: le righe devono arrivare sul file mentre gira.

Serve a una cosa sola, e non e' tecnica: chi guarda da un altro terminale deve
poter vedere che il lavoro sta andando. Prima il rapporto si scriveva solo alla
fine, e un giro da un'ora sembrava fermo.
"""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "agent"))
sys.path.insert(0, str(RADICE / "verifier"))

import agente


def test_scrive_su_schermo_e_su_file_riga_per_riga(tmp_path, capsys):
    registro = tmp_path / "sotto" / "registro.log"
    doppio = agente._Doppio(sys.stdout, registro)
    doppio.write("prima riga\n")
    # la riga deve essere GIA' sul file, senza aspettare la chiusura
    assert registro.read_text(encoding="utf-8") == "prima riga\n"
    doppio.write("seconda riga\n")
    assert registro.read_text(encoding="utf-8").count("\n") == 2
    doppio.flush()
    assert "prima riga" in capsys.readouterr().out


def test_crea_la_cartella_se_manca(tmp_path):
    registro = tmp_path / "a" / "b" / "c.log"
    agente._Doppio(sys.stdout, registro).write("x\n")
    assert registro.is_file()


def test_non_si_rompe_se_qualcuno_chiede_isatty(tmp_path):
    d = agente._Doppio(sys.stdout, tmp_path / "r.log")
    assert d.isatty() in (True, False)
