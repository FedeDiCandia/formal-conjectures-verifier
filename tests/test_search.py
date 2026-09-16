"""
Test dell'infrastruttura per le ricerche lunghe (verifier/search.py).

Le three cose che devono funzionare, perche' senza di esse one_ ricerca di otto
hours e' inutilizzabile:
  * l'isolamento (niente rete, niente scritture out_of dalla folder);
  * il checkpoint, scritto in way che un'interruzione non lo corrompa;
  * la ripresa, che deve ripartire da dove si era arrivati e non da capo.
"""
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import config
import search as search_module
import sandbox


def setup_module(module):
    if not sandbox.available():
        pytest.skip("sandbox-exec non available", allow_module_level=True)


#: Un program di ricerca minimum che rispetta il contratto.
COUNTING_PROGRAM = '''
import json, os, signal, sys, time

checkpoint = os.environ["SEARCH_CHECKPOINT"]
state = os.environ["SEARCH_STATE"]
FINO_A = int(os.environ.get("FINO_A", "50"))

n = 0
found = []
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    n = d.get("position", 0)
    found = d.get("found", [])

stopped = False
def stop_(s, f):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop_)

def salva():
    tmp = state + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"position": n, "examined": n, "found": found}, f)
    os.replace(tmp, state)

while n < FINO_A and not stopped:
    n += 1
    if n % 17 == 0:
        found.append({"n": n})
        print(json.dumps({"event": "found", "detail": {"n": n}}), flush=True)
    if n % 10 == 0:
        salva()
        print(json.dumps({"event": "progress", "position": n, "examined": n}), flush=True)
    time.sleep(float(os.environ.get("PAUSE", "0.01")))

salva()
print(json.dumps({"event": "end", "position": n, "examined": n}), flush=True)
'''


def test_una_ricerca_arriva_in_fondo(tmp_path):
    r = search_module.Search("prova_conta", COUNTING_PROGRAM, folder=tmp_path / "count_",
                               variables={"FINO_A": 50})
    result = r.run(verbose=False)
    assert result.completed, f"non completed: {result.to_json()}"
    assert result.position == 50
    assert result.examined == 50
    assert {"n": 17} in result.found
    assert {"n": 34} in result.found


def test_le_variabili_arrivano_al_programma(tmp_path):
    """L'environment del figlio e' minimum di proposito: niente key_ API, niente
    PATH del progetto. I parametri vanno passati esplicitamente."""
    program = """
import json, os
v = os.environ.get("MIO_PARAMETRO", "assente")
key_ = "presente" if "ANTHROPIC_API_KEY" in os.environ else "assente"
with open(os.environ["SEARCH_STATE"], "w") as f:
    json.dump({"position": v, "examined": 1, "found": [key_]}, f)
"""
    r = search_module.Search("prova_var", program, folder=tmp_path / "var",
                               variables={"MIO_PARAMETRO": "ciao"})
    result = r.run(verbose=False)
    assert result.position == "ciao"
    assert result.found == ["assente"], "la key_ API non deve essere visibile"


def test_il_checkpoint_viene_scritto(tmp_path):
    r = search_module.Search("prova_ckpt", COUNTING_PROGRAM, folder=tmp_path / "ckpt",
                               variables={"FINO_A": 30})
    r.run(verbose=False)
    assert r.checkpoint_file.is_file()
    d = json.loads(r.checkpoint_file.read_text())
    assert d["position"] == 30


def test_la_ripresa_riparte_da_dove_era_arrivata(tmp_path):
    """Il punto piu' importante: after un'interruzione non si ricomincia."""
    folder = tmp_path / "ripresa"
    r = search_module.Search("prova_ripresa", COUNTING_PROGRAM, folder=folder,
                               variables={"FINO_A": 100000, "PAUSE": 0.02})
    prime_ = r.run(max_seconds=2.0, verbose=False)
    assert prime_.interrupted, "mi aspettavo un'interruzione per tempo scaduto"
    assert prime_.position > 0, "deve aver fatto qualcosa before di fermarsi"
    arrivato = prime_.position

    # seconda esecuzione: deve RIPRENDERE
    r.variables = {"FINO_A": arrivato + 30, "PAUSE": 0.001}
    second_ = r.run(verbose=False)
    assert second_.completed
    assert second_.position == arrivato + 30
    # se fosse ripartita da zero, il tempo sarebbe state molto maggiore
    assert second_.examined == arrivato + 30


def test_riprendi_falso_ricomincia_da_capo(tmp_path):
    folder = tmp_path / "dacapo"
    r = search_module.Search("prova_dacapo", COUNTING_PROGRAM, folder=folder,
                               variables={"FINO_A": 20, "PAUSE": 0.001})
    r.run(verbose=False)
    r.variables = {"FINO_A": 10, "PAUSE": 0.001}
    second_ = r.run(resume=False, verbose=False)
    assert second_.position == 10, "con resume=False deve ripartire da zero"


NETWORK_PROGRAM = '''
import json, os, urllib.request
try:
    urllib.request.urlopen("http://example.com", timeout=5)
    print(json.dumps({"event": "found", "detail": "RETE ACCESSIBILE"}), flush=True)
except Exception as e:
    print(json.dumps({"event": "progress", "position": 0, "rete": type(e).__name__}), flush=True)
with open(os.environ["SEARCH_STATE"], "w") as f:
    json.dump({"position": 0, "examined": 0, "found": []}, f)
'''


def test_la_ricerca_non_ha_accesso_alla_rete(tmp_path):
    r = search_module.Search("prova_rete", NETWORK_PROGRAM, folder=tmp_path / "rete")
    result = r.run(verbose=False)
    assert "RETE ACCESSIBILE" not in str(result.found), "la rete deve essere bloccata"


WRITE_PROGRAM = '''
import json, os
target_ = os.environ.get("BERSAGLIO", "/tmp/prova_fuori.txt")
try:
    open(target_, "w").write("x")
    result = "SCRITTURA RIUSCITA"
except Exception as e:
    result = type(e).__name__
print(json.dumps({"event": "progress", "position": 0, "write_op": result}), flush=True)
with open(os.environ["SEARCH_STATE"], "w") as f:
    json.dump({"position": 0, "examined": 0, "found": [result]}, f)
'''


def test_la_ricerca_non_scrive_fuori_dalla_sua_cartella(tmp_path):
    r = search_module.Search("prova_scrittura", WRITE_PROGRAM,
                               folder=tmp_path / "write_op",
                               variables={"BERSAGLIO": str(config.ROOT / "PROVA_RICERCA_FUORI.txt")})
    result = r.run(verbose=False)
    assert "SCRITTURA RIUSCITA" not in str(result.found)
    assert not (config.ROOT / "PROVA_RICERCA_FUORI.txt").exists()


def test_la_ricerca_puo_usare_numpy_e_sympy(tmp_path):
    """L'environment di computation serve proprio a questo."""
    program = '''
import json, os
import numpy as np, sympy
v = int(np.sum(np.arange(101)))
p = int(sympy.prime(1000))
print(json.dumps({"event": "progress", "position": v, "prime_": p}), flush=True)
with open(os.environ["SEARCH_STATE"], "w") as f:
    json.dump({"position": v, "examined": 1, "found": [p]}, f)
'''
    r = search_module.Search("prova_librerie", program, folder=tmp_path / "lib")
    result = r.run(verbose=False)
    assert result.position == 5050, f"numpy: {result.to_json()}"
    assert 7919 in result.found, "sympy.prime(1000) = 7919"
