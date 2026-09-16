"""La compattazione del context: senza, un attempt lungo muore di context.

Test di only_ text, nessuna call all'API.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "verifier"))

import agent


def _conversation(n_iterations: int, length: int = 5000) -> list:
    """Una conversazione finta: statement, poi n rounds di strumento."""
    messages = [{"role": "user", "content": "ENUNCIATO DEL PROBLEM"}]
    for i in range(n_iterations):
        messages.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": f"t{i}", "name": "lean_check",
             "input": {"lean_code": f"theorem trial{i} : True := trivial"}}]})
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"t{i}",
             "content": "ERRORE " * (length // 7)}]})
    return messages


def test_accorcia_i_risultati_vecchi_e_lascia_intatti_i_recenti():
    m = _conversation(20)
    before = sum(len(b["content"]) for msg in m if isinstance(msg["content"], list)
                for b in msg["content"] if b.get("type") == "tool_result")
    cut_ = agent.compact_conversation(m, intact=8, queue=600)
    after = sum(len(b["content"]) for msg in m if isinstance(msg["content"], list)
               for b in msg["content"] if b.get("type") == "tool_result")
    assert cut_ > 0
    assert after < before / 3, f"compattazione inefficace: {before} -> {after}"
    # gli last_ones quattro results (inside gli 8 messages intact) sono interi
    last_ones = [b["content"] for msg in m[-8:] if isinstance(msg["content"], list)
              for b in msg["content"] if b.get("type") == "tool_result"]
    assert last_ones and all(len(c) > 600 for c in last_ones)


def test_l_enunciato_non_viene_mai_toccato():
    m = _conversation(20)
    agent.compact_conversation(m)
    assert m[0]["content"] == "ENUNCIATO DEL PROBLEM"


def test_il_codice_scritto_dal_modello_resta_intero():
    m = _conversation(20)
    agent.compact_conversation(m)
    for msg in m:
        if isinstance(msg["content"], list):
            for b in msg["content"]:
                if b.get("type") == "tool_use":
                    assert b["input"]["lean_code"].startswith("theorem trial")


def test_e_idempotente():
    m = _conversation(20)
    prime_ = agent.compact_conversation(m)
    second_ = agent.compact_conversation(m)
    assert prime_ > 0 and second_ == 0


def test_una_conversazione_corta_non_viene_toccata():
    m = _conversation(3)
    assert agent.compact_conversation(m, intact=8) == 0
