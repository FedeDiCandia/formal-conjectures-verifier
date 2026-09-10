"""
Propone i problemi migliori su cui collaudare il verificatore.

Cerca teoremi che soddisfano tutte queste condizioni:
  * l'archivio contiene gia' una dimostrazione completa (senza sorry);
  * l'enunciato non ha buchi answer( ) non proposizionali;
  * il file e' piccolo (piu' facile da capire e da compilare in fretta);
  * BONUS: l'enunciato usa una definizione dichiarata nello stesso file
    (serve al test "rifiuta chi ridefinisce una definizione dell'archivio").
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
from index import ProblemIndex

idx = ProblemIndex.load()
candidati = []
for p in idx.find(solved_here=True, has_answer_hole=False):
    src_file = p.source_file
    if not src_file.is_file():
        continue
    testo = src_file.read_text(encoding="utf-8")
    # definizioni dichiarate nel file stesso
    defs = re.findall(r"^\s*(?:noncomputable\s+)?(?:def|abbrev)\s+([\w'.]+)", testo, re.M)
    # quali di queste compaiono nell'enunciato?
    usate = [d for d in defs if d in p.statement]
    candidati.append({
        "teorema": p.theorem,
        "modulo": p.module,
        "categoria": p.category,
        "righe_file": testo.count("\n"),
        "def_locali_usate": usate,
        "teoremi_nel_file": len(re.findall(r"^\s*(?:theorem|lemma)\s", testo, re.M)),
    })

# prima quelli che usano una definizione locale, poi i file piu' piccoli
candidati.sort(key=lambda c: (not c["def_locali_usate"], c["righe_file"]))

print(f"Candidati totali: {len(candidati)}\n")
print("=== MIGLIORI (usano una definizione locale nell'enunciato) ===")
for c in [c for c in candidati if c["def_locali_usate"]][:12]:
    print(f"  {c['teorema']:45s} {c['righe_file']:4d} righe, "
          f"{c['teoremi_nel_file']:2d} teoremi, def usate: {c['def_locali_usate']}")
print("\n=== Piu' piccoli in assoluto ===")
for c in candidati[:12]:
    print(f"  {c['teorema']:45s} {c['righe_file']:4d} righe, "
          f"{c['teoremi_nel_file']:2d} teoremi, def usate: {c['def_locali_usate']}")
