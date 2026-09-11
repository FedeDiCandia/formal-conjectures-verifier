"""run_python: librerie di calcolo, persistenza, e isolamento ancora intatto."""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "agent"))
sys.path.insert(0, str(RADICE / "verifier"))

import pytest
import strumenti


def test_numpy_e_sympy_sono_disponibili(tmp_path):
    u = strumenti.esegui_run_python(
        "import numpy, sympy\nprint(sympy.isprime(1000003), numpy.arange(3).sum())",
        cartella=tmp_path)
    assert "True 3" in u, u


def test_i_file_sopravvivono_fra_due_chiamate(tmp_path):
    strumenti.esegui_run_python(
        "open('memoria.txt','w').write('2480')", cartella=tmp_path)
    u = strumenti.esegui_run_python(
        "print('letto', open('memoria.txt').read())", cartella=tmp_path)
    assert "letto 2480" in u, u


def test_senza_cartella_non_resta_niente():
    strumenti.esegui_run_python("open('memoria.txt','w').write('x')")
    u = strumenti.esegui_run_python(
        "import os; print('file presenti:', sorted(os.listdir('.')))")
    assert "memoria.txt" not in u, u


def test_la_rete_resta_bloccata(tmp_path):
    u = strumenti.esegui_run_python(
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('https://example.com', timeout=5)\n"
        "    print('RAGGIUNGIBILE')\n"
        "except Exception as e:\n"
        "    print('bloccata', type(e).__name__)\n", cartella=tmp_path)
    assert "bloccata" in u and "RAGGIUNGIBILE" not in u, u


def test_la_chiave_api_non_e_visibile(tmp_path):
    u = strumenti.esegui_run_python(
        "import os; print([k for k in os.environ if 'KEY' in k.upper()])",
        cartella=tmp_path)
    assert "[]" in u, u


def test_non_si_scrive_fuori_dalla_cartella(tmp_path):
    u = strumenti.esegui_run_python(
        f"try:\n"
        f"    open('{RADICE}/PROVA_VIETATA','w').write('x')\n"
        f"    print('SCRITTO')\n"
        f"except Exception as e:\n"
        f"    print('bloccato', type(e).__name__)\n", cartella=tmp_path)
    assert "bloccato" in u and "SCRITTO" not in u, u
    assert not (RADICE / "PROVA_VIETATA").exists()
