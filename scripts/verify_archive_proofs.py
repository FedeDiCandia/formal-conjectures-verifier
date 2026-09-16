"""
Submit the proofs the archive itself supplies to the verifier.

The axiom check (the `archiveProofAxioms` field) is necessary but not
sufficient: it does not say whether the proof, extracted from its file and compiled
on its own, really makes it through. Finding that out means trying, which is what
this script does.

A problem enters an agent's calibration ONLY if its archive proof is ACCEPTED
here. Otherwise asking an agent to solve it means asking it to do better than the
archive, and a failure would say
niente sull'agent.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

from index import ProblemIndex
from hide import _separator_position
import archive_proof
from verify import verify, SlotPool
import threading

idx = ProblemIndex.load()

def proof_lines(p) -> int:
    try:
        src = p.source_text()
        pos = _separator_position(src)
        return src[pos + 2:].strip().count("\n") + 1 if pos is not None else -1
    except Exception:
        return -1

names = sys.argv[1:] if len(sys.argv) > 1 else None
if names:
    chosen = [idx.get(n) for n in names]
else:
    chosen = [p for p in idx.find(archive_proof_clean=True)
              if not p.statement_has_sorry
              and p.category in ("research solved", "textbook")
              and proof_lines(p) > 0]

print(f"Problemi da verificare: {len(chosen)}\n", flush=True)

# Every module is brought up to date BEFORE starting: it is the only step that
# modifies the archive, and doing it during parallel verifications falsifies the
# fingerprint check.
from verify import prepare_challenge
print("Bringing the statements' modules up to date...", flush=True)
for p in chosen:
    ok, _ = prepare_challenge(p.module, 900)
    if not ok:
        print(f"  ATTENTION: {p.module} does not compile", flush=True)
print("  fatto\n", flush=True)

pool = SlotPool(4)
results = [None] * len(chosen)
avvio_globale = time.time()

def work(i, p):
    slot = pool.acquire()
    try:
        t0 = time.time()
        try:
            extracted = archive_proof.extract(p, idx)
        except archive_proof.NotExtractable as e:
            results[i] = {"problem": p.theorem, "result": "NON_ESTRAIBILE",
                            "reason": str(e), "seconds": 0}
            return
        tmp = Path(f"/tmp/archive_proof_run{slot}_{i}.lean")
        tmp.write_text(extracted.text, encoding="utf-8")
        try:
            r = verify(p.theorem, tmp, index=idx, slot=slot, timeout=900)
        finally:
            tmp.unlink(missing_ok=True)
        failed = [c.name for c in r.checks if not c.passed]
        results[i] = {
            "problem": p.theorem, "categoria": p.category,
            "proof_lines": proof_lines(p),
            "result": r.status, "controlli_falliti": failed,
            "errors": (r.errors or "")[:400],
            "theorems_removed": extracted.theorems_removed,
            "seconds": time.time() - t0,
            "assiomi_archivio": p.archive_proof_axioms,
        }
        state = "OK " if r.accepted else "NO "
        print(f"  [{state}] {p.theorem:58} {r.status:16} {time.time()-t0:5.0f}s", flush=True)
    finally:
        pool.release(slot)

threads = [threading.Thread(target=work, args=(i, p), daemon=True)
        for i, p in enumerate(chosen)]
for f in threads: f.start()
for f in threads: f.join()

results = [r for r in results if r]
ok = [r for r in results if r["result"] == "ACCEPTED"]
print(f"\n{'='*78}")
print(f"ACCETTATE: {len(ok)} su {len(results)}   "
      f"(tempo total {time.time()-avvio_globale:.0f}s)")
print(f"{'='*78}")
for r in results:
    if r["result"] != "ACCEPTED":
        print(f"  RIFIUTATA  {r['problem']}")
        print(f"             {r['result']}  {r.get('controlli_falliti')}")
        if r.get("errors"):
            print(f"             {r['errors'].strip().splitlines()[0][:110]}")

dest = Path(__file__).resolve().parent.parent / "runs" / "archive_proofs.json"
dest.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nsalvato in {dest}")
