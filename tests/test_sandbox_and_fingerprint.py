"""
Test dell'isolamento della verifica e del controllo di integrita' dell'archivio.

DUE DIFESE DISTINTE
-------------------
1. `sandbox-exec` impedisce al codice del candidato di scrivere fuori dalla
   cartella del modulo temporaneo e di accedere alla rete.
2. L'fingerprint dell'archivio, confrontata prima e dopo ogni verifica, si accorge
   se qualcosa e' cambiato comunque.

La seconda serve anche se la prima funziona: `sandbox-exec` e' deprecato da
Apple, e su Linux (dove andrebbe usato il vero `landrun`) il codice prende
un'altra strada. Un controllo che non dipende dal meccanismo di isolamento vale
piu' di uno che gli si fida.

PERCHE' L'IMPRONTA CONTA DAVVERO
--------------------------------
comparator esporta il Challenge PRIMA di compilare la Solution. Quindi un
sabotaggio durante la compilazione del candidato non altera la verifica in
corso: altera quelle SUCCESSIVE. E' esattamente l'assunto 2 del README di
comparator ("non devi aver GIA' compilato file potenzialmente ostili"). Noi
facciamo verifiche a ripetizione nella stessa cartella, quindi quell'assunto va
controllato, non dato per buono.
"""
import copy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))

import config
import fingerprint as fingerprint_module
import sandbox


def setup_module(module):
    if not sandbox.disponibile():
        pytest.skip("sandbox-exec non disponibile su questo sistema", allow_module_level=True)
    if not config.ARCHIVE.is_dir():
        pytest.skip("archivio non clonato", allow_module_level=True)


@pytest.fixture
def profilo(tmp_path):
    scrivibili = sandbox.cartelle_scrivibili(config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_path)
    for d in scrivibili:
        d.mkdir(parents=True, exist_ok=True)
    return sandbox.scrivi_profilo(tmp_path / "prova.sb", scrivibili, RADICE)


def _prova_scrittura(percorso: Path, profilo: Path | None) -> bool:
    """Tenta di scrivere `percorso`. Ritorna True se ci riesce."""
    percorso.unlink(missing_ok=True)
    comando = ["/bin/sh", "-c", f'echo prova > "{percorso}"']
    if profilo is not None:
        comando = sandbox.avvolgi(comando, profilo)
    subprocess.run(comando, capture_output=True, text=True)
    riuscito = percorso.exists()
    percorso.unlink(missing_ok=True)
    return riuscito


# --- la sandbox --------------------------------------------------------------

def test_senza_sandbox_la_scrittura_nell_archivio_riesce():
    """La controprova. Senza questo test, i due successivi non dimostrerebbero
    che e' la sandbox a fermare le scritture: potrebbero essere bloccate da
    qualcos'altro (permessi del filesystem, per esempio)."""
    assert _prova_scrittura(config.ARCHIVE / "PROVA_CONTROPROVA.txt", None), \
        "senza sandbox la scrittura deve riuscire, altrimenti il test non prova nulla"


def test_la_sandbox_blocca_le_scritture_nell_archivio(profilo):
    assert not _prova_scrittura(config.ARCHIVE / "PROVA_SANDBOX.txt", profilo)


def test_la_sandbox_blocca_le_scritture_sui_file_compilati(profilo):
    """Il bersaglio che conta: i file compilati da cui comparator legge
    l'enunciato originale."""
    compilati = config.ARCHIVE / ".lake" / "build" / "lib" / "lean" / "FormalConjectures"
    if not compilati.is_dir():
        pytest.skip("archivio non compilato")
    assert not _prova_scrittura(compilati / "PROVA_SANDBOX.olean", profilo)


def test_la_sandbox_consente_le_scritture_dove_servono(profilo):
    """Se bloccasse anche queste, nessuna verifica potrebbe funzionare."""
    dentro = config.ARCHIVE / config.SANDBOX_SUBDIR / "prova_permesso.txt"
    assert _prova_scrittura(dentro, profilo)


def test_la_sandbox_blocca_la_rete(profilo):
    comando = sandbox.avvolgi(
        ["/usr/bin/curl", "-s", "-m", "8", "-o", "/dev/null", "https://example.com"], profilo)
    esito = subprocess.run(comando, capture_output=True, text=True)
    assert esito.returncode != 0, "curl non deve riuscire a raggiungere la rete"


# --- l'fingerprint --------------------------------------------------------------

def test_l_impronta_e_stabile():
    a = fingerprint_module.calcola(config.ARCHIVE)
    b = fingerprint_module.calcola(config.ARCHIVE)
    assert a.n_file_contenuto > 100, "mi aspetto centinaia di file dell'archivio"
    assert not fingerprint_module.confronta(a, b), \
        "due impronte consecutive senza modifiche devono coincidere"


def test_l_impronta_rileva_un_file_modificato():
    a = fingerprint_module.calcola(config.ARCHIVE)
    b = copy.deepcopy(a)
    quale = next(iter(b.contenuto))
    b.contenuto[quale] = "0" * 64
    differenze = fingerprint_module.confronta(a, b)
    assert differenze and "MODIFICATI" in differenze[0]
    assert quale in differenze[0]


def test_l_impronta_rileva_un_file_cancellato():
    a = fingerprint_module.calcola(config.ARCHIVE)
    b = copy.deepcopy(a)
    b.contenuto.pop(next(iter(b.contenuto)))
    assert any("CANCELLATI" in d for d in fingerprint_module.confronta(a, b))


def test_l_impronta_rileva_un_cambio_nelle_dipendenze():
    a = fingerprint_module.calcola(config.ARCHIVE)
    b = copy.deepcopy(a)
    b.metadati_dipendenze = "0" * 64
    assert any("Mathlib" in d for d in fingerprint_module.confronta(a, b))


def test_l_impronta_ignora_la_cartella_del_modulo_temporaneo():
    """La cartella del candidato cambia a ogni verifica: se la contassimo,
    ogni verifica segnalerebbe un falso allarme."""
    cartella = config.ARCHIVE / config.SANDBOX_SUBDIR
    cartella.mkdir(parents=True, exist_ok=True)
    a = fingerprint_module.calcola(config.ARCHIVE, escludi=cartella.name)
    intruso = cartella / "S99.lean"
    intruso.write_text("-- file temporaneo\n", encoding="utf-8")
    try:
        b = fingerprint_module.calcola(config.ARCHIVE, escludi=cartella.name)
        assert not fingerprint_module.confronta(a, b)
    finally:
        intruso.unlink(missing_ok=True)
