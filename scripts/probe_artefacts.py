"""
Cerca le formalizzazioni che cedono per un finding, non per matematica.

DA DOVE VIENE QUESTA IDEA
-------------------------
Leggendo le soluzioni ACCETTATE del benchmark OEIS Open di Epoch AI si vede che
il loro 30% di successi non è tutto matematica. Tre esempi reali, dai loro file:

  * `A211420_general_divisibility_conjecture` dimostrato con
    `exact ⟨0, fun n => by simp⟩`: l'statement diceva «esiste C tale che per
    ogni n ... divide C * a(n)», e con C = 0 è vero per niente. La congettura
    matematica non è quella.
  * `A262403_conjecture_ii_distinctness` confutato perché π(T 0) = π(T 1) = 0:
    l'iniettività cade su two cases al bordo.
  * `A070823_conjecture` confutato con un counterexample piccolo (n = 20),
    found calcolando e verificato con `decide`.

Le prime two sono **formalizzazioni sbagliate**, da segnalare agli autori
dell'archive e non da spacciare per results; la terza è un counterexample
vero. Tutte e three si trovano con tattiche a cost zero, senza API.

PERCHÉ UN SOLO FILE PER PROBLEM
--------------------------------
Ogni compilazione paga ~6 seconds di import di Mathlib. Provare venti tattiche
in venti file costa venti volte quell'waited; metterle nello stesso file la paga
one volta sola. Le dichiarazioni in Lean sono indipendenti: se one non si closes
l'error riguarda lei, e le other_items proseguono. Si risale da ogni message alla
tactic che l'ha prodotto tramite la line.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "scripts"))

import config as verifier_config   # noqa: E402
import explore                          # noqa: E402
from index import ProblemIndex          # noqa: E402

#: (name, tactic, anche_sulla_negazione). L'order non count piu': si compila
#: tutto insieme.
TACTICS = [
    ("testimone_zero",   "exact ⟨0, by simp⟩",            False),
    ("testimone_zero_d", "exact ⟨0, by decide⟩",          False),
    ("testimone_vuoto",  "exact ⟨∅, by simp⟩",            False),
    ("simp",             "simp",                          True),
    ("simp_arith",       "simp +arith",                   True),
    ("decide",           "decide",                        True),
    ("norm_num",         "norm_num",                      True),
    ("omega",            "omega",                         True),
    ("aesop",            "aesop",                         True),
    ("trivial",          "trivial",                       True),
    ("plausible",        "plausible",                     True),
]


def build(problem, heartbeats: int) -> tuple[str, dict[str, tuple[str, bool]]]:
    """Il file con all_items le trials, e la mapping name del theorem -> (tactic, negated).

    Dopo ogni trial il file chiede a Lean **gli axioms** di quella trial. È il
    criterio decisivo, ed è lo stesso del verifier: one tactic ha chiuso
    davvero l'statement only se la declaration che ne risulta NON dipende da
    `sorryAx`. Contare i messages di error non basta — one tactic che falliva
    produceva a volte un error attribuito a un'altra line, e la trial sembrava
    riuscita. Con `#print axioms` la answer arriva per name, non per position.
    """
    lines = [f"import {verifier_config.utility_module()}",
             f"import {problem.module}", ""]
    mapping: dict[str, tuple[str, bool]] = {}
    # Il `@` e' obbligatorio: senza, Lean istanzia gli arguments
    # impliciti come metavariabili e la probe trial un statement DIVERSO
    # da quello dell'archive. Senza di esso `aesop` "confutava" la
    # congettura di Agrawal, e il verifier vero rifiutava la stessa
    # dimostrazione: era il quarto falso positivo di questa specie.
    kind = f"type_of% @{problem.theorem}"
    for name, tactic, also_negated in TACTICS:
        for negated in (False, True) if also_negated else (False,):
            statement = f"¬ ({kind})" if negated else kind
            theorem = f"probe{name}{'_neg' if negated else ''}"
            mapping[theorem] = (name, negated)
            lines.append(f"set_option maxHeartbeats {heartbeats} in")
            lines.append(f"theorem {theorem} : {statement} := by")
            lines.append(f"  {tactic}")
            lines.append(f"#print axioms {theorem}")
            lines.append("")
    return "\n".join(lines) + "\n", mapping


#: `#print axioms name` show one line di questa forma.
_RE_AXIOMS = re.compile(r"'(\S+)' depends on axioms: \[([^\]]*)\]")
_RE_SENZA = re.compile(r"'(\S+)' does not depend on any axioms")
_RE_COUNTEREXAMPLE = re.compile(r"Found a counter-example", re.I)


def read(output: str, mapping: dict[str, tuple[str, bool]]) -> dict:
    """Assegna a ogni tactic il suo result leggendo gli axioms, per name.

    Regola: one tactic ha CHIUSO l'statement se la declaration corrispondente
    esiste e non dipende da `sorryAx`. Se dipende da `sorryAx` la tactic non ha
    dimostrato niente — è il caso di `plausible`, che quando non trova
    controesempi lascia un `sorry` e fa compilare il file comunque. Se la
    declaration non compare fra gli axioms stampati, la trial è fallita before
    di arrivare a esistere.
    """
    axioms: dict[str, set[str]] = {}
    for line in output.split("\n"):
        m = _RE_AXIOMS.search(line)
        if m:
            axioms[m.group(1)] = {a.strip() for a in m.group(2).split(",") if a.strip()}
            continue
        m = _RE_SENZA.search(line)
        if m:
            axioms[m.group(1)] = set()
    counterexample = bool(_RE_COUNTEREXAMPLE.search(output))
    # Un file che non compila puo' comunque stampare one line di axioms pulita per
    # one declaration la cui elaborazione e' stata salvata: e' il caso di
    # Erdos628.erdos_628, dove `aesop` risultava "chiusa, nessun assioma" mentre il
    # file aveva un error di notazione e il verifier ha poi risposto
    # REJECTED: il file non compila. La probe non deve mai mostrare un result
    # positivo senza questo avviso accanto.
    errors = [r for r in output.split("\n") if " error: " in r or r.startswith("error:")]

    results = []
    for theorem, (name, negated) in mapping.items():
        ax = axioms.get(theorem)
        if ax is None:
            result, detail = "aperta", "la declaration non esiste: la tactic ha failed"
        elif "sorryAx" in ax:
            result, detail = "aperta", "dipende da sorryAx: non ha dimostrato niente"
        else:
            result = "confutata" if negated else "chiusa"
            detail = "axioms: " + (", ".join(sorted(ax)) or "nessuno")
            if errors:
                detail = (f"ATTENZIONE: il file contiene {len(errors)} errors di "
                             f"compilazione, quindi questo result non vale niente "
                             f"finche' il verifier non dice ACCEPTED. "
                             f"Primo error: {errors[0].strip()[:160]}. " + detail)
        results.append({"tactic": name, "negated": negated, "result": result,
                      "detail": detail})
    if counterexample:
        results.append({"tactic": "plausible", "negated": None,
                      "result": "counterexample",
                      "detail": "plausible ha esibito un counterexample: "
                                   "vedi i messages grezzi"})
    return {"trials": results}


def check_environment(targets: Path) -> None:
    """I targets e l'archive devono venire dallo stesso snapshot.

    Quinto falso positivo: la probe girava con l'index predefinito (bench-v1)
    mentre i targets erano chosen su `main`. Gli import fallivano, i messages di
    Lean erano spazzatura, e il lettore ci leggeva inside dei successi.
    """
    data = json.loads(targets.read_text(encoding="utf-8"))
    expected = data.get("snapshot", "")
    current_one = str(verifier_config.ARCHIVE)
    if "fc-main" in expected and "fc-main" not in current_one:
        raise SystemExit(
            f"AMBIENTE SBAGLIATO.\n"
            f"  i targets sono stati chosen su: {expected}\n"
            f"  l'archive in uso e':           {current_one}\n"
            f"Rilancia con:\n"
            f"  env FCS_ARCHIVE=$PWD/external/fc-main \\\n"
            f"      FCS_LEAN4EXPORT=$PWD/external/lean4export-433/.lake/build/bin/lean4export \\\n"
            f"      FCS_INDEX=$PWD/verifier/problem_index_main.json \\\n"
            f"    ./.venv/bin/python scripts/probe_artefacts.py")


def confirm_with_verifier(problem, tactic: str, negated: bool,
                              timeout: int) -> tuple[str, str]:
    """Sottopone la trial al verifier vero. Ritorna (result, detail).

    E' l'unico giudizio che count. Il candidato e' scritto nella forma che
    `verify.py` si aspetta: in mode' confutazione gli e' permesso importare
    il module del problem (e appoggiarsi alla sua dimostrazione non serve,
    perche' e' un `sorry` e il controllo degli axioms lo rifiuta).
    """
    import tempfile
    from verify import verify, REFUTATION, STRICT
    body = (f"import {verifier_config.utility_module()}\n"
             f"import {problem.module}\n\n")
    if negated:
        name = f"{problem.theorem}_refutation"
        body += (f"theorem {name} : ¬ (type_of% @{problem.theorem}) := by\n"
                  f"  {tactic}\n")
        mode = REFUTATION
    else:
        name = f"{problem.theorem}_riprova"
        body += (f"theorem {name} : type_of% @{problem.theorem} := by\n"
                  f"  {tactic}\n")
        mode = STRICT
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False,
                                    encoding="utf-8") as fh:
        fh.write(body)
        path = Path(fh.name)
    try:
        r = verify(problem.theorem, path, mode=mode,
                   run_guard=False, timeout=timeout)
        return r.status, (r.message or "")[:300]
    finally:
        path.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default=str(ROOT / "docs/data/targets.json"))
    ap.add_argument("--how_many", type=int, default=0, help="0 = all_items")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--heartbeats", type=int, default=200000)
    ap.add_argument("--output", default=str(ROOT / "runs/hunt/artefacts.json"))
    args = ap.parse_args()

    check_environment(Path(args.targets))
    idx = ProblemIndex.load()
    data = json.loads(Path(args.targets).read_text(encoding="utf-8"))
    chosen = []
    for c in data["candidates"]:
        try:
            chosen.append(idx.get(c["problem"]))
        except Exception:
            continue

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else []
    seen = {v["problem"] for v in results}
    chosen = [p for p in chosen if p.theorem not in seen]
    if args.how_many:
        chosen = chosen[:args.how_many]

    print(f"Sondo {len(chosen)} enunciati, {len(TACTICS)} tattiche in UN file ciascuno.")
    print(f"Gia' fatti: {len(seen)}. Nessuna spesa API.\n", flush=True)

    notable = 0
    for i, p in enumerate(chosen, 1):
        t0 = time.time()
        code, mapping = build(p, args.heartbeats)
        r = explore.explore(code, timeout=args.timeout)
        entry = {"problem": p.theorem, "module": p.module,
                "statement": p.statement[:300], "seconds": round(time.time() - t0, 1)}
        if r.rejected_by_guard:
            entry["error"] = f"guard: {r.rejected_by_guard}"
        else:
            entry.update(read(r.messages, mapping))
            candidates = [x for x in entry["trials"]
                         if x["result"] in ("chiusa", "confutata", "counterexample")]
            if candidates:
                entry["messaggi_grezzi"] = r.messages[:20000]
                entry["candidates"] = []
                for x in candidates:
                    if x["result"] == "counterexample":
                        continue          # un counterexample non e' one trial
                    tactic = dict((n, t) for n, t, _ in TACTICS)[x["tactic"]]
                    print(f"  ? {p.theorem}: {x['tactic']}"
                          f"{' (negata)' if x['negated'] else ''} sembra chiudere — "
                          f"lo sottopongo al verifier...", flush=True)
                    result, detail = confirm_with_verifier(
                        p, tactic, x["negated"], args.timeout * 4)
                    entry["candidates"].append(
                        {"tactic": x["tactic"], "negated": x["negated"],
                         "verifier": result, "detail": detail})
                    print(f"    -> verifier: {result}", flush=True)
                    if result == "ACCEPTED":
                        entry["ATTENZIONE"] = (
                            f"{x['tactic']}{' (negata)' if x['negated'] else ''} "
                            f"ACCETTATA DAL VERIFICATORE")
                if "ATTENZIONE" in entry:
                    notable += 1
                    print(f"  !!! {p.theorem}: {entry['ATTENZIONE']}", flush=True)
        results.append(entry)
        output.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"[{i}/{len(chosen)}] {p.theorem[:54]:54} "
              f"{'NOTEVOLE' if 'ATTENZIONE' in entry else '.':9} {entry['seconds']:6.0f}s",
              flush=True)

    print(f"\n{'='*70}\nEsaminati {len(chosen)}. Notevoli: {notable}\nRisultati in {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
