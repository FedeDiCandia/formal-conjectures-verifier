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
        "open('memory.txt','w').write('2480')", folder=tmp_path)
    u = tools.run_python_tool(
        "print('read', open('memory.txt').read())", folder=tmp_path)
    assert "read 2480" in u, u


def test_without_a_directory_nothing_remains():
    tools.run_python_tool("open('memory.txt','w').write('x')")
    u = tools.run_python_tool(
        "import os; print('files present:', sorted(os.listdir('.')))")
    assert "memory.txt" not in u, u


def test_the_network_stays_blocked(tmp_path):
    u = tools.run_python_tool(
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('https://example.com', timeout=5)\n"
        "    print('REACHABLE')\n"
        "except Exception as e:\n"
        "    print('blocked', type(e).__name__)\n", folder=tmp_path)
    assert "blocked" in u and "REACHABLE" not in u, u


def test_the_api_key_is_not_visible(tmp_path):
    u = tools.run_python_tool(
        "import os; print([k for k in os.environ if 'KEY' in k.upper()])",
        folder=tmp_path)
    assert "[]" in u, u


def test_nothing_is_written_outside_the_directory(tmp_path):
    u = tools.run_python_tool(
        f"try:\n"
        f"    open('{ROOT}/FORBIDDEN_WRITE_TRIAL','w').write('x')\n"
        f"    print('WRITTEN')\n"
        f"except Exception as e:\n"
        f"    print('blocked', type(e).__name__)\n", folder=tmp_path)
    assert "blocked" in u and "WRITTEN" not in u, u
    assert not (ROOT / "FORBIDDEN_WRITE_TRIAL").exists()
