"""
Propone i problemi migliori su cui collaudare l'agente.

Il criterio decisivo non e' "l'archivio lo ha risolto", ma **la dimostrazione
dell'archivio passerebbe il nostro verificatore**. Sono due cose diverse: 87
dimostrazioni dell'archivio usano `decide +native`, che lascia l'assioma
`Lean.ofReduceBool`, e il verificatore le rifiuta a ragione. Chiedere a un
agente di risolvere uno di quei problemi significherebbe chiedergli di fare
meglio dell'archivio, e un fallimento non direbbe niente sull'agente.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
from index import ProblemIndex

idx = ProblemIndex.load()

print(f"Teoremi nell'indice: {len(idx)}\n")

solved = idx.find(solved_here=True)
puliti = idx.find(archive_proof_clean=True)
print(f"Con dimostrazione completa nell'archivio:      {len(solved)}")
print(f"  di cui accettabili dal nostro verificatore:  {len(puliti)}")
sporchi = [p for p in solved if not p.archive_proof_is_clean]
if sporchi:
    from collections import Counter
    motivi = Counter(a for p in sporchi for a in p.archive_proof_forbidden_axioms)
    print(f"  le altre {len(sporchi)} usano assiomi non ammessi:")
    for a, n in motivi.most_common():
        print(f"      {a}: {n}")

candidati = []
for p in puliti:
    if p.statement_has_sorry:
        continue
    if p.category not in ("research solved", "textbook"):
        continue
    src_file = p.source_file
    if not src_file.is_file():
        continue
    testo = src_file.read_text(encoding="utf-8")
    defs = re.findall(r"^\s*(?:noncomputable\s+)?(?:def|abbrev)\s+([\w'.]+)", testo, re.M)
    usate = [d for d in defs if d in p.statement]
    try:
        prova = p.source_text()
        righe_prova = prova.count("\n") + 1
    except Exception:
        righe_prova = 0
    candidati.append({
        "p": p,
        "righe_file": testo.count("\n"),
        "righe_dichiarazione": righe_prova,
        "def_locali_usate": usate,
        "teoremi_nel_file": len(re.findall(r"^\s*(?:theorem|lemma)\s", testo, re.M)),
        "car_enunciato": len(p.statement),
    })

candidati.sort(key=lambda c: (c["righe_dichiarazione"], c["car_enunciato"]))

print(f"\n{'='*78}")
print(f"CANDIDATI AL COLLAUDO: {len(candidati)}")
print("(gia' risolti nell'archivio, dimostrazione pulita per il kernel,")
print(" nessun buco answer( ), categoria research solved o textbook)")
print(f"{'='*78}")
print(f"{'righe':>5} {'enunc.':>6}  {'categoria':16} nome")
for c in candidati[:25]:
    p = c["p"]
    marchio = " *" if c["def_locali_usate"] else "  "
    print(f"{c['righe_dichiarazione']:5d} {c['car_enunciato']:6d}  {p.category:16} {p.theorem}{marchio}")
print("\n  * = l'enunciato usa una definizione dichiarata nello stesso file")
