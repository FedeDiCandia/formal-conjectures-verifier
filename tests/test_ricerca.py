"""
Test dell'infrastruttura per le ricerche lunghe (verifier/ricerca.py).

Le tre cose che devono funzionare, perche' senza di esse una ricerca di otto
ore e' inutilizzabile:
  * l'isolamento (niente rete, niente scritture fuori dalla cartella);
  * il checkpoint, scritto in modo che un'interruzione non lo corrompa;
  * la ripresa, che deve ripartire da dove si era arrivati e non da capo.
"""
import json
import sys
import time
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))

import config
import ricerca as modulo_ricerca
import sandbox


def setup_module(module):
    if not sandbox.disponibile():
        pytest.skip("sandbox-exec non disponibile", allow_module_level=True)


#: Un programma di ricerca minimo che rispetta il contratto.
PROGRAMMA_CONTA = '''
import json, os, signal, sys, time

checkpoint = os.environ["RICERCA_CHECKPOINT"]
stato = os.environ["RICERCA_STATO"]
FINO_A = int(os.environ.get("FINO_A", "50"))

n = 0
trovati = []
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    n = d.get("posizione", 0)
    trovati = d.get("trovati", [])

fermati = False
def arresto(s, f):
    global fermati
    fermati = True
signal.signal(signal.SIGTERM, arresto)

def salva():
    tmp = stato + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"posizione": n, "esaminati": n, "trovati": trovati}, f)
    os.replace(tmp, stato)

while n < FINO_A and not fermati:
    n += 1
    if n % 17 == 0:
        trovati.append({"n": n})
        print(json.dumps({"evento": "trovato", "dettaglio": {"n": n}}), flush=True)
    if n % 10 == 0:
        salva()
        print(json.dumps({"evento": "progresso", "posizione": n, "esaminati": n}), flush=True)
    time.sleep(float(os.environ.get("PAUSA", "0.01")))

salva()
print(json.dumps({"evento": "fine", "posizione": n, "esaminati": n}), flush=True)
'''


def test_una_ricerca_arriva_in_fondo(tmp_path):
    r = modulo_ricerca.Ricerca("prova_conta", PROGRAMMA_CONTA, cartella=tmp_path / "conta",
                               variabili={"FINO_A": 50})
    esito = r.esegui(verboso=False)
    assert esito.conclusa, f"non conclusa: {esito.to_json()}"
    assert esito.posizione == 50
    assert esito.esaminati == 50
    assert {"n": 17} in esito.trovati
    assert {"n": 34} in esito.trovati


def test_le_variabili_arrivano_al_programma(tmp_path):
    """L'ambiente del figlio e' minimo di proposito: niente chiave API, niente
    PATH del progetto. I parametri vanno passati esplicitamente."""
    programma = """
import json, os
v = os.environ.get("MIO_PARAMETRO", "assente")
chiave = "presente" if "ANTHROPIC_API_KEY" in os.environ else "assente"
with open(os.environ["RICERCA_STATO"], "w") as f:
    json.dump({"posizione": v, "esaminati": 1, "trovati": [chiave]}, f)
"""
    r = modulo_ricerca.Ricerca("prova_var", programma, cartella=tmp_path / "var",
                               variabili={"MIO_PARAMETRO": "ciao"})
    esito = r.esegui(verboso=False)
    assert esito.posizione == "ciao"
    assert esito.trovati == ["assente"], "la chiave API non deve essere visibile"


def test_il_checkpoint_viene_scritto(tmp_path):
    r = modulo_ricerca.Ricerca("prova_ckpt", PROGRAMMA_CONTA, cartella=tmp_path / "ckpt",
                               variabili={"FINO_A": 30})
    r.esegui(verboso=False)
    assert r.file_checkpoint.is_file()
    d = json.loads(r.file_checkpoint.read_text())
    assert d["posizione"] == 30


def test_la_ripresa_riparte_da_dove_era_arrivata(tmp_path):
    """Il punto piu' importante: dopo un'interruzione non si ricomincia."""
    cartella = tmp_path / "ripresa"
    r = modulo_ricerca.Ricerca("prova_ripresa", PROGRAMMA_CONTA, cartella=cartella,
                               variabili={"FINO_A": 100000, "PAUSA": 0.02})
    primo = r.esegui(secondi_massimi=2.0, verboso=False)
    assert primo.interrotta, "mi aspettavo un'interruzione per tempo scaduto"
    assert primo.posizione > 0, "deve aver fatto qualcosa prima di fermarsi"
    arrivato = primo.posizione

    # seconda esecuzione: deve RIPRENDERE
    r.variabili = {"FINO_A": arrivato + 30, "PAUSA": 0.001}
    secondo = r.esegui(verboso=False)
    assert secondo.conclusa
    assert secondo.posizione == arrivato + 30
    # se fosse ripartita da zero, il tempo sarebbe stato molto maggiore
    assert secondo.esaminati == arrivato + 30


def test_riprendi_falso_ricomincia_da_capo(tmp_path):
    cartella = tmp_path / "dacapo"
    r = modulo_ricerca.Ricerca("prova_dacapo", PROGRAMMA_CONTA, cartella=cartella,
                               variabili={"FINO_A": 20, "PAUSA": 0.001})
    r.esegui(verboso=False)
    r.variabili = {"FINO_A": 10, "PAUSA": 0.001}
    secondo = r.esegui(riprendi=False, verboso=False)
    assert secondo.posizione == 10, "con riprendi=False deve ripartire da zero"


PROGRAMMA_RETE = '''
import json, os, urllib.request
try:
    urllib.request.urlopen("http://example.com", timeout=5)
    print(json.dumps({"evento": "trovato", "dettaglio": "RETE ACCESSIBILE"}), flush=True)
except Exception as e:
    print(json.dumps({"evento": "progresso", "posizione": 0, "rete": type(e).__name__}), flush=True)
with open(os.environ["RICERCA_STATO"], "w") as f:
    json.dump({"posizione": 0, "esaminati": 0, "trovati": []}, f)
'''


def test_la_ricerca_non_ha_accesso_alla_rete(tmp_path):
    r = modulo_ricerca.Ricerca("prova_rete", PROGRAMMA_RETE, cartella=tmp_path / "rete")
    esito = r.esegui(verboso=False)
    assert "RETE ACCESSIBILE" not in str(esito.trovati), "la rete deve essere bloccata"


PROGRAMMA_SCRITTURA = '''
import json, os
bersaglio = os.environ.get("BERSAGLIO", "/tmp/prova_fuori.txt")
try:
    open(bersaglio, "w").write("x")
    esito = "SCRITTURA RIUSCITA"
except Exception as e:
    esito = type(e).__name__
print(json.dumps({"evento": "progresso", "posizione": 0, "scrittura": esito}), flush=True)
with open(os.environ["RICERCA_STATO"], "w") as f:
    json.dump({"posizione": 0, "esaminati": 0, "trovati": [esito]}, f)
'''


def test_la_ricerca_non_scrive_fuori_dalla_sua_cartella(tmp_path):
    r = modulo_ricerca.Ricerca("prova_scrittura", PROGRAMMA_SCRITTURA,
                               cartella=tmp_path / "scrittura",
                               variabili={"BERSAGLIO": str(config.ROOT / "PROVA_RICERCA_FUORI.txt")})
    esito = r.esegui(verboso=False)
    assert "SCRITTURA RIUSCITA" not in str(esito.trovati)
    assert not (config.ROOT / "PROVA_RICERCA_FUORI.txt").exists()


def test_la_ricerca_puo_usare_numpy_e_sympy(tmp_path):
    """L'ambiente di calcolo serve proprio a questo."""
    programma = '''
import json, os
import numpy as np, sympy
v = int(np.sum(np.arange(101)))
p = int(sympy.prime(1000))
print(json.dumps({"evento": "progresso", "posizione": v, "primo": p}), flush=True)
with open(os.environ["RICERCA_STATO"], "w") as f:
    json.dump({"posizione": v, "esaminati": 1, "trovati": [p]}, f)
'''
    r = modulo_ricerca.Ricerca("prova_librerie", programma, cartella=tmp_path / "lib")
    esito = r.esegui(verboso=False)
    assert esito.posizione == 5050, f"numpy: {esito.to_json()}"
    assert 7919 in esito.trovati, "sympy.prime(1000) = 7919"
