"""Configurazione comune ai test: rende importabili i moduli di verifier/."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
