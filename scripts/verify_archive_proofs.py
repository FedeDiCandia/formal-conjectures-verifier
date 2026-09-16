"""
Sottopone al verificatore le dimostrazioni che l'archivio stesso fornisce.

Il controllo sugli assiomi (campo `archiveProofAxioms`) e' necessario ma non
sufficiente: non dice se la dimostrazione, estratta dal suo file e compilata da
sola, arriva davvero in fondo. Per saperlo bisogna provarci, ed e' quello che
fa questo script.

Un problema entra nella calibrazione di un agent SOLO se la sua dimostrazione
d'archivio viene ACCETTATA qui. Altrimenti chiedere a un agent di risolverlo
significa chiedergli di fare meglio dell'archivio, e un fallimento non direbbe
niente sull'agent.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

from index import ProblemIndex
from hide import _posizione_separatore
import archive_proof
from verify import verify, SlotPool
import threading

idx = ProblemIndex.load()

def righe_prova(p) -> int:
    try:
        src = p.source_text()
        pos = _posizione_separatore(src)
        return src[pos + 2:].strip().count("\n") + 1 if pos is not None else -1
    except Exception:
        return -1

nomi = sys.argv[1:] if len(sys.argv) > 1 else None
if nomi:
    scelti = [idx.get(n) for n in nomi]
else:
    scelti = [p for p in idx.find(archive_proof_clean=True)
              if not p.statement_has_sorry
              and p.category in ("research solved", "textbook")
              and righe_prova(p) > 0]

print(f"Problemi da verificare: {len(scelti)}\n", flush=True)

# Si portano in pari tutti i moduli PRIMA di cominciare: e' l'unico passo che
# modifica l'archivio, e farlo durante le verifiche parallele falsa il
# controllo dell'fingerprint.
from verify import prepara_sfida
print("Porto in pari i moduli degli enunciati...", flush=True)
for p in scelti:
    ok, _ = prepara_sfida(p.module, 900)
    if not ok:
        print(f"  ATTENZIONE: {p.module} non compila", flush=True)
print("  fatto\n", flush=True)

pool = SlotPool(4)
risultati = [None] * len(scelti)
avvio_globale = time.time()

def lavora(i, p):
    slot = pool.acquire()
    try:
        t0 = time.time()
        try:
            estratto = archive_proof.estrai(p, idx)
        except archive_proof.NonEstraibile as e:
            risultati[i] = {"problema": p.theorem, "esito": "NON_ESTRAIBILE",
                            "motivo": str(e), "secondi": 0}
            return
        tmp = Path(f"/tmp/prova_archivio_{slot}_{i}.lean")
        tmp.write_text(estratto.testo, encoding="utf-8")
        try:
            r = verify(p.theorem, tmp, index=idx, slot=slot, timeout=900)
        finally:
            tmp.unlink(missing_ok=True)
        falliti = [c.name for c in r.checks if not c.passed]
        risultati[i] = {
            "problema": p.theorem, "categoria": p.category,
            "righe_prova": righe_prova(p),
            "esito": r.status, "controlli_falliti": falliti,
            "errori": (r.errors or "")[:400],
            "teoremi_rimossi": estratto.teoremi_rimossi,
            "secondi": time.time() - t0,
            "assiomi_archivio": p.archive_proof_axioms,
        }
        stato = "OK " if r.accepted else "NO "
        print(f"  [{stato}] {p.theorem:58} {r.status:16} {time.time()-t0:5.0f}s", flush=True)
    finally:
        pool.release(slot)

fili = [threading.Thread(target=lavora, args=(i, p), daemon=True)
        for i, p in enumerate(scelti)]
for f in fili: f.start()
for f in fili: f.join()

risultati = [r for r in risultati if r]
ok = [r for r in risultati if r["esito"] == "ACCETTATO"]
print(f"\n{'='*78}")
print(f"ACCETTATE: {len(ok)} su {len(risultati)}   "
      f"(tempo totale {time.time()-avvio_globale:.0f}s)")
print(f"{'='*78}")
for r in risultati:
    if r["esito"] != "ACCETTATO":
        print(f"  RIFIUTATA  {r['problema']}")
        print(f"             {r['esito']}  {r.get('controlli_falliti')}")
        if r.get("errori"):
            print(f"             {r['errori'].strip().splitlines()[0][:110]}")

dest = Path(__file__).resolve().parent.parent / "runs" / "prove_archivio.json"
dest.write_text(json.dumps(risultati, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nsalvato in {dest}")
