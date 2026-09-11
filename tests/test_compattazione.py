"""La compattazione del contesto: senza, un tentativo lungo muore di contesto.

Test di solo testo, nessuna chiamata all'API.
"""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "agent"))
sys.path.insert(0, str(RADICE / "verifier"))

import agente


def _conversazione(n_iterazioni: int, lunghezza: int = 5000) -> list:
    """Una conversazione finta: enunciato, poi n giri di strumento."""
    messaggi = [{"role": "user", "content": "ENUNCIATO DEL PROBLEMA"}]
    for i in range(n_iterazioni):
        messaggi.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": f"t{i}", "name": "lean_check",
             "input": {"codice_lean": f"theorem prova{i} : True := trivial"}}]})
        messaggi.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"t{i}",
             "content": "ERRORE " * (lunghezza // 7)}]})
    return messaggi


def test_accorcia_i_risultati_vecchi_e_lascia_intatti_i_recenti():
    m = _conversazione(20)
    prima = sum(len(b["content"]) for msg in m if isinstance(msg["content"], list)
                for b in msg["content"] if b.get("type") == "tool_result")
    tagliati = agente.compatta_conversazione(m, intatti=8, coda=600)
    dopo = sum(len(b["content"]) for msg in m if isinstance(msg["content"], list)
               for b in msg["content"] if b.get("type") == "tool_result")
    assert tagliati > 0
    assert dopo < prima / 3, f"compattazione inefficace: {prima} -> {dopo}"
    # gli ultimi quattro risultati (dentro gli 8 messaggi intatti) sono interi
    ultimi = [b["content"] for msg in m[-8:] if isinstance(msg["content"], list)
              for b in msg["content"] if b.get("type") == "tool_result"]
    assert ultimi and all(len(c) > 600 for c in ultimi)


def test_l_enunciato_non_viene_mai_toccato():
    m = _conversazione(20)
    agente.compatta_conversazione(m)
    assert m[0]["content"] == "ENUNCIATO DEL PROBLEMA"


def test_il_codice_scritto_dal_modello_resta_intero():
    m = _conversazione(20)
    agente.compatta_conversazione(m)
    for msg in m:
        if isinstance(msg["content"], list):
            for b in msg["content"]:
                if b.get("type") == "tool_use":
                    assert b["input"]["codice_lean"].startswith("theorem prova")


def test_e_idempotente():
    m = _conversazione(20)
    primo = agente.compatta_conversazione(m)
    secondo = agente.compatta_conversazione(m)
    assert primo > 0 and secondo == 0


def test_una_conversazione_corta_non_viene_toccata():
    m = _conversazione(3)
    assert agente.compatta_conversazione(m, intatti=8) == 0
