"""
Test dell'isolamento della check e del controllo di integrita' dell'archive.

DUE DIFESE DISTINTE
-------------------
1. `sandbox-exec` impedisce al code del candidato di scrivere out_of dalla
   folder del module temporaneo e di accedere alla rete.
2. L'fingerprint dell'archive, confrontata before e after ogni check, si accorge
   se qualcosa e' cambiato comunque.

La seconda serve also_ se la before funziona: `sandbox-exec` e' deprecato da
Apple, e su Linux (dove andrebbe usato il vero `landrun`) il code prende
un'altra strada. Un controllo che non dipende dal meccanismo di isolamento vale
piu' di one che gli si fida.

PERCHE' L'IMPRONTA CONTA DAVVERO
--------------------------------
comparator esporta il Challenge PRIMA di compilare la Solution. Quindi un
sabotaggio durante la compilazione del candidato non altera la check in
corso: altera quelle SUCCESSIVE. E' esattamente l'assunto 2 del README di
comparator ("non devi aver GIA' compilato file potenzialmente ostili"). Noi
facciamo checks a ripetizione nella stessa folder, quindi quell'assunto va
controllato, non dato per buono.
"""
import copy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import config
import fingerprint as fingerprint_module
import sandbox


def setup_module(module):
    if not sandbox.available():
        pytest.skip("sandbox-exec non available su questo system", allow_module_level=True)
    if not config.ARCHIVE.is_dir():
        pytest.skip("archive non clonato", allow_module_level=True)


@pytest.fixture
def profile(tmp_path):
    writable = sandbox.writable_dirs(config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_path)
    for d in writable:
        d.mkdir(parents=True, exist_ok=True)
    return sandbox.write_profile(tmp_path / "trial.sb", writable, ROOT)


def _write_test(path: Path, profile: Path | None) -> bool:
    """Tenta di scrivere `path`. Ritorna True se ci riesce."""
    path.unlink(missing_ok=True)
    command = ["/bin/sh", "-c", f'echo trial > "{path}"']
    if profile is not None:
        command = sandbox.wrap(command, profile)
    subprocess.run(command, capture_output=True, text=True)
    succeeded = path.exists()
    path.unlink(missing_ok=True)
    return succeeded


# --- la sandbox --------------------------------------------------------------

def test_senza_sandbox_la_scrittura_nell_archivio_riesce():
    """La controprova. Senza questo test, i two successivi non dimostrerebbero
    che e' la sandbox a fermare le scritture: potrebbero essere bloccate da
    qualcos'other (permissions del filesystem, per example)."""
    assert _write_test(config.ARCHIVE / "PROVA_CONTROPROVA.txt", None), \
        "senza sandbox la write_op deve riuscire, altrimenti il test non trial nulla"


def test_la_sandbox_blocca_le_scritture_nell_archivio(profile):
    assert not _write_test(config.ARCHIVE / "PROVA_SANDBOX.txt", profile)


def test_la_sandbox_blocca_le_scritture_sui_file_compilati(profile):
    """Il target_ che count_: i file compiled da cui comparator legge
    l'statement original."""
    compiled = config.ARCHIVE / ".lake" / "build" / "lib" / "lean" / "FormalConjectures"
    if not compiled.is_dir():
        pytest.skip("archive non compilato")
    assert not _write_test(compiled / "PROVA_SANDBOX.olean", profile)


def test_la_sandbox_consente_le_scritture_dove_servono(profile):
    """Se bloccasse also_ queste, nessuna check potrebbe funzionare."""
    inside = config.ARCHIVE / config.SANDBOX_SUBDIR / "prova_permesso.txt"
    assert _write_test(inside, profile)


def test_la_sandbox_blocca_la_rete(profile):
    command = sandbox.wrap(
        ["/usr/bin/curl", "-s", "-m", "8", "-o", "/dev/null", "https://example.com"], profile)
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0, "curl non deve riuscire a raggiungere la rete"


# --- l'fingerprint --------------------------------------------------------------

def test_l_impronta_e_stabile():
    a = fingerprint_module.compute(config.ARCHIVE)
    b = fingerprint_module.compute(config.ARCHIVE)
    assert a.n_content_files > 100, "mi aspetto centinaia di file dell'archive"
    assert not fingerprint_module.compare(a, b), \
        "two impronte consecutive senza modifiche devono coincidere"


def test_l_impronta_rileva_un_file_modificato():
    a = fingerprint_module.compute(config.ARCHIVE)
    b = copy.deepcopy(a)
    which = next(iter(b.content))
    b.content[which] = "0" * 64
    differences = fingerprint_module.compare(a, b)
    assert differences and "MODIFICATI" in differences[0]
    assert which in differences[0]


def test_l_impronta_rileva_un_file_cancellato():
    a = fingerprint_module.compute(config.ARCHIVE)
    b = copy.deepcopy(a)
    b.content.pop(next(iter(b.content)))
    assert any("CANCELLATI" in d for d in fingerprint_module.compare(a, b))


def test_l_impronta_rileva_un_cambio_nelle_dipendenze():
    a = fingerprint_module.compute(config.ARCHIVE)
    b = copy.deepcopy(a)
    b.dependency_metadata = "0" * 64
    assert any("Mathlib" in d for d in fingerprint_module.compare(a, b))


def test_l_impronta_ignora_la_cartella_del_modulo_temporaneo():
    """La folder del candidato cambia a ogni check: se la contassimo,
    ogni check segnalerebbe un falso allarme."""
    folder = config.ARCHIVE / config.SANDBOX_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    a = fingerprint_module.compute(config.ARCHIVE, exclude=folder.name)
    intruder = folder / "S99.lean"
    intruder.write_text("-- file temporaneo\n", encoding="utf-8")
    try:
        b = fingerprint_module.compute(config.ARCHIVE, exclude=folder.name)
        assert not fingerprint_module.compare(a, b)
    finally:
        intruder.unlink(missing_ok=True)
