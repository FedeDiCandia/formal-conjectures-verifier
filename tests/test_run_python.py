"""run_python: the computation libraries, persistence, and isolation still intact."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "verifier"))

import pytest
import tools


def test_numpy_and_sympy_are_available(tmp_path):
    u = tools.run_python_tool(
        "import numpy, sympy\nprint(sympy.isprime(1000003), numpy.arange(3).sum())",
        folder=tmp_path)
    assert "True 3" in u, u


def test_files_survive_between_two_calls(tmp_path):
    tools.run_python_tool(
        "open('memoria.txt','w').write('2480')", folder=tmp_path)
    u = tools.run_python_tool(
        "print('letto', open('memoria.txt').read())", folder=tmp_path)
    assert "letto 2480" in u, u


def test_without_a_directory_nothing_remains():
    tools.run_python_tool("open('memoria.txt','w').write('x')")
    u = tools.run_python_tool(
        "import os; print('file presenti:', sorted(os.listdir('.')))")
    assert "memoria.txt" not in u, u


def test_the_network_stays_blocked(tmp_path):
    u = tools.run_python_tool(
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('https://example.com', timeout=5)\n"
        "    print('RAGGIUNGIBILE')\n"
        "except Exception as e:\n"
        "    print('bloccata', type(e).__name__)\n", folder=tmp_path)
    assert "bloccata" in u and "RAGGIUNGIBILE" not in u, u


def test_the_api_key_is_not_visible(tmp_path):
    u = tools.run_python_tool(
        "import os; print([k for k in os.environ if 'KEY' in k.upper()])",
        folder=tmp_path)
    assert "[]" in u, u


def test_nothing_is_written_outside_the_directory(tmp_path):
    u = tools.run_python_tool(
        f"try:\n"
        f"    open('{ROOT}/PROVA_VIETATA','w').write('x')\n"
        f"    print('SCRITTO')\n"
        f"except Exception as e:\n"
        f"    print('bloccato', type(e).__name__)\n", folder=tmp_path)
    assert "bloccato" in u and "SCRITTO" not in u, u
    assert not (ROOT / "PROVA_VIETATA").exists()
