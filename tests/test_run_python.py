"""run_python: librerie di computation, persistenza, e isolamento ancora intatto."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "verifier"))

import pytest
import tools


def test_numpy_e_sympy_sono_disponibili(tmp_path):
    u = tools.run_python_tool(
        "import numpy, sympy\nprint(sympy.isprime(1000003), numpy.arange(3).sum())",
        folder=tmp_path)
    assert "True 3" in u, u


def test_i_file_sopravvivono_fra_due_chiamate(tmp_path):
    tools.run_python_tool(
        "open('memoria.txt','w').write('2480')", folder=tmp_path)
    u = tools.run_python_tool(
        "print('letto', open('memoria.txt').read())", folder=tmp_path)
    assert "letto 2480" in u, u


def test_senza_cartella_non_resta_niente():
    tools.run_python_tool("open('memoria.txt','w').write('x')")
    u = tools.run_python_tool(
        "import os; print('file presenti:', sorted(os.listdir('.')))")
    assert "memoria.txt" not in u, u


def test_la_rete_resta_bloccata(tmp_path):
    u = tools.run_python_tool(
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('https://example.com', timeout=5)\n"
        "    print('RAGGIUNGIBILE')\n"
        "except Exception as e:\n"
        "    print('bloccata', type(e).__name__)\n", folder=tmp_path)
    assert "bloccata" in u and "RAGGIUNGIBILE" not in u, u


def test_la_chiave_api_non_e_visibile(tmp_path):
    u = tools.run_python_tool(
        "import os; print([k for k in os.environ if 'KEY' in k.upper()])",
        folder=tmp_path)
    assert "[]" in u, u


def test_non_si_scrive_fuori_dalla_cartella(tmp_path):
    u = tools.run_python_tool(
        f"try:\n"
        f"    open('{ROOT}/PROVA_VIETATA','w').write('x')\n"
        f"    print('SCRITTO')\n"
        f"except Exception as e:\n"
        f"    print('bloccato', type(e).__name__)\n", folder=tmp_path)
    assert "bloccato" in u and "SCRITTO" not in u, u
    assert not (ROOT / "PROVA_VIETATA").exists()
