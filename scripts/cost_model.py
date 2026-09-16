"""
FASE C — model dei costi e proiezione sui problems open_problems.

Ogni number stampato porta un'label:

  MISURATO   viene da un'esecuzione registrata su file in questo repository.
  STIMATO    e' un'ipotesi. Accanto c'e' sempre il reasoning che la regge.

Il model non usa librerie esterne: l'intervallo di confidence_level e' quello di
Clopper-Pearson, calcolato per bisezione sulla total_sum binomiale esatta, cosi'
non serve scipy e il conto e' riproducibile da chiunque legga il code.

Uso:  python3 scripts/cost_model.py > runs/fase_c.txt
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
from index import ProblemIndex   # noqa: E402

LEVELS = ("facile", "mean", "difficile")
SPEND_LEVELS = (50, 100, 200, 500, 1000, 5000)


# ---------------------------------------------------------------- statistica
def _binom_upper_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) per X ~ Binomiale(n, p). Somma esatta, nessuna libreria."""
    return sum(math.comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k, n + 1))


def _binom_lower_tail(k: int, n: int, p: float) -> float:
    """P(X <= k)."""
    return sum(math.comb(n, i) * p**i * (1 - p)**(n - i) for i in range(0, k + 1))


def _bisection(f, target: float, lo: float, hi: float) -> float:
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, confidence_level: float = 0.90) -> tuple[float, float]:
    """Intervallo di Clopper-Pearson per one proporzione k/n.

    E' l'intervallo che non assume niente sulla forma della distribuzione:
    con numbers piccoli resta wide, ed e' giusto che residues wide.
    """
    alfa = 1 - confidence_level
    low = 0.0 if k == 0 else _bisection(
        lambda p: _binom_upper_tail(k, n, p), alfa / 2, 0.0, 1.0)
    high = 1.0 if k == n else _bisection(
        lambda p: 1 - _binom_lower_tail(k, n, p), 1 - alfa / 2, 0.0, 1.0)
    return low, high


# ---------------------------------------------------------------- data
def load() -> dict:
    data = {}
    data["cal"] = json.loads(
        (ROOT / "docs/data/calibration_full.json").read_text(encoding="utf-8"))

    idx = {}
    for name, perc in (("bench-v1", "verifier/problem_index.json"),
                       ("main", "verifier/problem_index_main.json")):
        i = ProblemIndex.load(ROOT / perc)
        open_problems = i.find(category="research open")
        ap_ver = [p for p in open_problems if not p.statement_has_sorry]
        ris = i.find(category="research solved")
        idx[name] = {
            "theorems": len(i.problems),
            "open_problems": len(open_problems),
            "aperti_verificabili": len(ap_ver),
            "aperti_con_buco_non_prop": len(open_problems) - len(ap_ver),
            "aperti_confutabili": len([p for p in open_problems
                                       if p.answer_placeholder_in_source
                                       and not p.statement_has_sorry]),
            "aperti_varianti": len([p for p in ap_ver if ".variants." in p.theorem]),
            "solved": len(ris),
            "risolti_con_prova_pulita": len([p for p in ris if p.archive_proof_is_clean]),
            "risolti_senza_prova": len([p for p in ris if not p.proof_is_complete
                                        and not p.statement_has_sorry]),
            "prove_complete": len([p for p in i.problems if p.proof_is_complete]),
            "prove_pulite": len([p for p in i.problems if p.archive_proof_is_clean]),
        }
    data["index"] = idx

    # before la copia versionata in docs/data, cosi' la report_text si rigenera
    # also su un computer dove runs/ non c'e' (runs/ non e' below git)
    probe = next((p for p in (ROOT / "docs/data/probe_lean.json",
                              ROOT / "runs/hunt/probe_lean.json") if p.is_file()),
                 None)
    data["probe"] = json.loads(probe.read_text(encoding="utf-8")) if probe else None

    caccia = []
    for folder in sorted((ROOT / "runs/hunt").glob("*/")):
        f = folder / "state.json"
        g = folder / "result.json"
        entry = {"name": folder.name}
        for key, path in (("state", f), ("result", g)):
            if path.is_file():
                entry[key] = json.loads(path.read_text(encoding="utf-8"))
        if len(entry) > 1:
            caccia.append(entry)
    data["hunt"] = caccia
    return data


# ---------------------------------------------------------------- model
def per_level(problems: list[dict]) -> dict:
    outside = {}
    for lvl in LEVELS:
        group = [p for p in problems if p["level"] == lvl]
        if not group:
            continue
        solved = [p for p in group if p["solved"]]
        failed = [p for p in group if not p["solved"]]
        low, high = clopper_pearson(len(solved), len(group))
        outside[lvl] = {
            "n": len(group), "solved": len(solved),
            "rate": len(solved) / len(group),
            "intervallo": (low, high),
            "costo_successo": [p["cost"] for p in solved],
            "costo_fallimento": [p["cost"] for p in failed],
            "iterazioni_successo": [p["iterations"] for p in solved],
            "seconds": [p["seconds"] for p in group],
        }
    return outside


def cost_per_success(p: float, c_successo: float, c_fallimento: float) -> float:
    """Costo expected per ottenere UN successo, con attempts indipendenti."""
    if p <= 0:
        return float("inf")
    return (c_successo * p + c_fallimento * (1 - p)) / p


def tabella_proiezione(name: str, c_tentativo: float, p: float) -> list[tuple]:
    lines = []
    for b in SPEND_LEVELS:
        n = b / c_tentativo
        lines.append((b, n, n * p))
    return lines


def fmt(x: float) -> str:
    if x == float("inf"):
        return "infinito"
    if x == 0:
        return "0"
    if x >= 1000:
        return f"{x:,.0f}".replace(",", " ")
    if x >= 10:
        return f"{x:.0f}"
    if x >= 1:
        return f"{x:.1f}"
    return f"{x:.3f}"


# ---------------------------------------------------------------- scenari
#
# Questi sono gli UNICI numbers inventati del model. Ognuno porta la sua
# motivazione, e la motivazione dice su which misura si appoggia.

SCENARIOS = {
    "A": {
        "name": "dimostrazioni Lean dirette su enunciati open_problems",
        "ottimistico": (0.02,
            "la probe automatica non ha chiuso nessuno dei 30 enunciati open_problems "
            "provati (240 trials): il limit superiore misurato al 90% e' 9,5%. "
            "Prendo circa un quinto di quel cap, perche' la probe trial "
            "tattiche mentre l'agent ragiona — quindi puo' fare meglio — ma "
            "9,5% e' il cap di un sample di 30, non one estimate"),
        "realistico": (0.003,
            "un successo ogni ~300 attempts: la calibrazione misura 5/7 su "
            "varianti GIA' dimostrate in archive (trials di 10-34 lines), ma "
            "nessun aperto ha one trial corta note, per definition di aperto"),
        "pessimistico": (0.0002,
            "un successo ogni 5000: l'archive e' curato da DeepMind per "
            "raccogliere problems su cui gli esperti si sono stopped"),
    },
    "B": {
        "name": "ricerca di counterexamples con computation local",
        "ottimistico": (0.05,
            "one minoranza di congetture ha bounds verified bassi (per la "
            "congettura di Selfridge la letteratura si ferma a k~29): su quelle "
            "il computation local arriva davvero oltre il noto"),
        "realistico": (0.01,
            "misurato in questo progetto: 0 findings su 3 ricerche e "
            "~2 hours-CPU; la ricerca sui numbers di Euclide ha exceeded 2,5 "
            "milioni di primes senza niente"),
        "pessimistico": (0.001,
            "i bounds pubblicati sono quasi sempre outside portata: per il "
            "problem di Erdos 366 la check arriva a 10^22"),
    },
    "C": {
        "name": "strategia mista: setaccio a low cost, poi affondo",
        "ottimistico": (None, "derivato da A e B"),
        "realistico": (None, "derivato da A e B"),
        "pessimistico": (None, "derivato da A e B"),
    },
}


# Parametri della strategia mista. Sono three numbers, declared qui.
DIVE_SHARE = 0.10       # STIMATO: su 10 problems setacciati, 1 merita l'affondo
AMPLIFICATION = {"ottimistico": 3.0, "realistico": 2.0, "pessimistico": 1.0}
FIRST_SHOT_SHARE = 0.22   # MISURATO: 2 dei 9 successi sono arrivati alla before
                           # iteration (Wilson, ClaudesCycles)

# Strategia B: how_many targets esistono davvero.
N_SELECTED_HUNT = 30          # MISURATO: runs/hunt/selection.json
REACHABLE_FRONTIER_FRACTION = 0.50   # STIMATO su 2 letterature su 4 controllate

# Che cosa hanno fatto le ricerche lanciate. I findings sono ZERO in all_items e
# three: la entry `found` di erdos396 contiene valori CALCOLATI (il minimum n per
# ogni k), non counterexamples, e va letta cosi'.
HUNT = {
    "euclide_squarefree": (
        "un first p con p^2 che divide un number di Euclide",
        "conclusiva: un only ritrovamento confuterebbe la congettura", 0),
    "erdos409_sigma": (
        "orbits di n -> sigma(n)-1 che non toccano mai un first",
        "trova suspects da esaminare a mano, non confutazioni", 0),
    "erdos396_binomiale": (
        "il minimum n con descFactorial(n,k+1) che divide centralBinom(n)",
        "raccoglie indizi: la forma 'per ogni k esiste n' non e' confutabile "
        "da un computation", 0),
}


def report_text(data: dict) -> str:
    r: list[str] = []
    def p(s: str = "") -> None:
        r.append(s)

    cal = data["cal"]
    problems = cal["problems"]
    idx = data["index"]
    lvl = per_level(problems)

    solved = [x for x in problems if x["solved"]]
    failed = [x for x in problems if not x["solved"]]
    c_succ = st.mean(x["cost"] for x in solved)
    c_fall = st.mean(x["cost"] for x in failed)
    c_it1 = st.median(x["costo_it1"] for x in problems)

    p("# Fase C — model dei costi e proiezione sui problems open_problems")
    p()
    p(f"Generato da `scripts/cost_model.py`. Modello **{cal['model']}**, "
      f"effort **{cal['effort']}**, snapshot `{cal['snapshot']}`.")
    p()

    # ---------------------------------------------------------------- 1
    p("## 1. Che cosa e' state misurato")
    p()
    p(f"**MISURATO** — {len(problems)} problems tentati, {len(solved)} solved, "
      f"spesa total ${cal['spesa_totale']:.4f}. Tutti entrati nell'archive "
      f"after il cut di addestramento dichiarato ({cal['taglio_addestramento']}), "
      f"all_items con la dimostrazione d'archive accepted dal verifier, "
      f"all_items con la dimostrazione nascosta all'agent.")
    p()
    p("| level | lines di trial | result | iter. | espl. | checks | seconds | cost |")
    p("|---|---|---|---|---|---|---|---|")
    for x in problems:
        p(f"| {x['level']} | {x['proof_lines']} | "
          f"{'**solved**' if x['solved'] else 'non solved'} | "
          f"{x['iterations']} | {x['explorations']} | {x['checks']} | "
          f"{x['seconds']} | ${x['cost']:.4f} |")
    p()

    # ---------------------------------------------------------------- 2
    p("## 2. Il model, level per level")
    p()
    p("Il rate di successo e' accompagnato dall'intervallo di Clopper-Pearson "
      "al 90%: con quattro o cinque problems per level l'intervallo e' larghissimo, "
      "e dichiararlo e' l'unico way onesto di dare il number.")
    p()
    p("| level | n | solved | rate | intervallo 90% | cost mean se solved | cost se failed |")
    p("|---|---|---|---|---|---|---|")
    for name, v in lvl.items():
        cs = f"${st.mean(v['costo_successo']):.4f}" if v["costo_successo"] else "—"
        cf = (f"${st.mean(v['costo_fallimento']):.4f}" if v["costo_fallimento"] else "—")
        p(f"| {name} | {v['n']} | {v['solved']} | {v['rate']:.0%} | "
          f"{v['intervallo'][0]:.0%} – {v['intervallo'][1]:.0%} | {cs} | {cf} |")
    tot_b, tot_a = clopper_pearson(len(solved), len(problems))
    p(f"| **total** | {len(problems)} | {len(solved)} | "
      f"{len(solved)/len(problems):.0%} | {tot_b:.0%} – {tot_a:.0%} | "
      f"${c_succ:.4f} | ${c_fall:.4f} |")
    p()
    p("**MISURATO** — le quattro entries di level `facile` sono problems di "
      "categoria `test`, cioe' controlli di sanita' scritti dagli autori "
      "dell'archive: 4 su 4. Le sette entries `mean` e `difficile` sono varianti "
      "di congetture vere e proprie, di categoria `research solved`: 5 su 7. "
      "Il number da ricordare e' **5 su 7**, non 9 su 11.")
    p()
    p(f"**MISURATO** — cost mean di un successo ${c_succ:.4f}; "
      f"cost mean di un failure ${c_fall:.4f}. Un failure costa "
      f"{c_fall/c_succ:.0f} volte un successo, perche' il failure consuma "
      f"tutto il cap per problem mentre il successo si ferma appena la "
      f"dimostrazione passa.")
    p()
    p(f"**MISURATO** — cost della PRIMA iteration, mediana su {len(problems)} "
      f"problems: ${c_it1:.4f}. Due dei nove successi sono arrivati proprio alla "
      f"before iteration. Questo e' il prezzo di un colpo only, e serve alla "
      f"strategia mista del punto 4.")
    p()
    ore_lean = sum(x["lean_seconds"] for x in problems) / 3600
    ore_tot = sum(x["seconds"] for x in problems) / 3600
    p(f"**MISURATO** — tempo di calendario: {ore_tot:.2f} hours in tutto, di cui "
      f"{ore_lean:.2f} hours di Lean in local ({100*ore_lean/ore_tot:.0f}%). "
      f"Il collo di bottiglia non e' l'API: e' il verifier.")
    p()
    p("### Costo per problem solved")
    p()
    p("Formula: (cost se solved x p + cost se failed x (1-p)) / p, cioe' quanto "
      "costa in media arrivare a UN successo ritentando su problems diversi.")
    p()
    p("| level | p | cost per successo | con p al minimum dell'intervallo | al maximum |")
    p("|---|---|---|---|---|")
    for name, v in lvl.items():
        cs = st.mean(v["costo_successo"]) if v["costo_successo"] else c_succ
        cf = st.mean(v["costo_fallimento"]) if v["costo_fallimento"] else c_fall
        a = cost_per_success(v["rate"], cs, cf)
        b = cost_per_success(v["intervallo"][0], cs, cf)
        c = cost_per_success(v["intervallo"][1], cs, cf)
        p(f"| {name} | {v['rate']:.0%} | ${fmt(a)} | ${fmt(b)} | ${fmt(c)} |")
    p()
    return r

def report_part_two(data: dict, r: list[str]) -> list[str]:
    def p(s: str = "") -> None:
        r.append(s)

    cal = data["cal"]
    problems = cal["problems"]
    idx = data["index"]
    solved = [x for x in problems if x["solved"]]
    failed = [x for x in problems if not x["solved"]]
    c_succ = st.mean(x["cost"] for x in solved)
    c_fall = st.mean(x["cost"] for x in failed)
    c_it1 = st.median(x["costo_it1"] for x in problems)

    # ---------------------------------------------------------------- 3
    p("## 3. Quanti targets ci sono")
    p()
    p("| | bench-v1 | main (0a8b856c) |")
    p("|---|---|---|")
    entries = [
        ("theorems indicizzati", "theorems"),
        ("`research open`", "open_problems"),
        ("open_problems con statement full (verificabili)", "aperti_verificabili"),
        ("open_problems con buco `answer( )` non proposizionale", "aperti_con_buco_non_prop"),
        ("open_problems attaccabili per confutazione", "aperti_confutabili"),
        ("open_problems che sono varianti ausiliarie", "aperti_varianti"),
        ("`research solved`", "solved"),
        ("solved con dimostrazione pulita in archive", "risolti_con_prova_pulita"),
        ("solved SENZA dimostrazione in archive", "risolti_senza_prova"),
    ]
    for label, key in entries:
        p(f"| {label} | {idx['bench-v1'][key]} | {idx['main'][key]} |")
    p()
    p("Tutti **MISURATI** sull'index built da Lean.")
    p()
    p("I conteggi di `main` valgono con la semantica `google.answer = "
      "always_true`, quella predefinita, in cui `answer(sorry) ↔ P` diventa "
      "`True ↔ P` e il problem e' davvero dimostrabile. Fino a questa sessione "
      "lo snapshot dichiarava also one seconda libreria che compilava gli "
      "stessi file con `postpone`, e i two insiemi di `.olean` si sovrascrivevano "
      "a vicenda: con quella semantica gli stessi 94 problems non sono "
      "attaccabili affatto. La libreria in eccesso e' stata disattivata — vedi "
      "`docs/01` — e i numbers qui above sono quelli della semantica giusta.")
    p()
    p(f"Due osservazioni che cambiano la strategia. Primo: **nessuno** dei "
      f"{idx['main']['open_problems']} problems marcati `research open` ha one "
      f"dimostrazione complete in archive — l'archive e' coerente con se stesso, "
      f"non ci sono open_problems 'per distrazione' da raccogliere. Secondo: "
      f"{idx['main']['risolti_senza_prova']} problems sono marcati `research solved` "
      f"ma non hanno alcuna dimostrazione Lean in archive: la matematica e' note, "
      f"la formalizzazione manca. Quella e' one terza classe di targets, piu' "
      f"facile degli open_problems e piu' difficile di quelli su cui ho calibrato.")
    p()

    # ---------------------------------------------------------------- 4
    p("## 4. Proiezione sui problems open_problems")
    p()
    p("Le probabilita' di successo su un problem **aperto** non sono misurabili: "
      "sono le three ipotesi qui below, e ogni line dichiara su cosa si appoggia. "
      "I conti tengono conto del fatto che i targets sono in number **finito**: "
      "quando one strategia li ha esauriti, la spesa in piu' non compra niente "
      "che questo model sappia valutare.")
    p()
    n_targets = idx["main"]["aperti_verificabili"]
    c_a = c_fall
    c_s = c_it1
    c_b = 0.10

    p("### Costo di un attempt (base del conto)")
    p()
    p(f"- **A, affondo full** su un statement aperto: **${c_a:.2f}** — "
      f"**MISURATO**, media dei two fallimenti della calibrazione "
      f"(${failed[0]['cost']:.4f} fermato dalle 20 iterations, "
      f"${failed[1]['cost']:.4f} fermato dal cap di spesa). Su un aperto il "
      f"attempt finisce quasi sempre cosi'.")
    p(f"- **C, colpo only** (setaccio): **${c_s:.4f}** — **MISURATO**, mediana "
      f"del cost della before iteration sugli 11 problems della calibrazione.")
    p(f"- **B, program di ricerca** scritto e lanciato: **${c_b:.2f}** di API "
      f"per problem — **STIMATO**, dell'order del cost misurato dei problems "
      f"facili (media "
      f"${st.mean(x['cost'] for x in problems if x['level']=='facile'):.4f}). "
      f"Il computation local non costa dollari: costa notti di macchina.")
    p()

    # ------------------------------------------------- A
    p("### Strategia A — dimostrazioni Lean dirette su enunciati open_problems")
    p()
    p(f"Un affondo per problem, chosen a caso tra i {n_targets} open_problems "
      f"verificabili. Saturazione a **${fmt(n_targets*c_a)}**.")
    p()
    p("| spesa | affondi | ottimistico | realistico | pessimistico |")
    p("|---|---|---|---|---|")
    for b in SPEND_LEVELS:
        n = min(b / c_a, n_targets)
        note = " *(saturo)*" if b / c_a > n_targets else ""
        cells = [fmt(n * SCENARIOS["A"][sc][0])
                 for sc in ("ottimistico", "realistico", "pessimistico")]
        p(f"| ${b} | {fmt(n)}{note} | {cells[0]} | {cells[1]} | {cells[2]} |")
    p()
    for sc in ("ottimistico", "realistico", "pessimistico"):
        prob, reason = SCENARIOS["A"][sc]
        p(f"- **{sc}: p = {prob:.2%}** — STIMATO. {reason}.")
    p()

    # ------------------------------------------------- B
    idonei_totali = N_SELECTED_HUNT
    reachable_share = REACHABLE_FRONTIER_FRACTION
    n_b = idonei_totali * reachable_share
    p("### Strategia B — ricerca di counterexamples con computation local")
    p()
    p(f"Qui il limit non e' il denaro: e' il number di problems su cui one "
      f"ricerca ha senso. **MISURATO**: lo script di selection ne ha found "
      f"{idonei_totali} adatti al computation su tutto l'archive. Dei quattro di cui "
      f"ho controllato la letteratura, two hanno one frontier raggiungibile "
      f"(numbers di Euclide: nessuna ricerca sistematica pubblicata; congettura di "
      f"Selfridge: verificata only fino a k circa 29) e two no (Erdos 366: "
      f"verificata fino a 10^22; Goldbach e Legendre: fino a 4x10^18). Due su "
      f"quattro, intervallo di Clopper-Pearson al 90% "
      f"{clopper_pearson(2,4)[0]:.0%} – {clopper_pearson(2,4)[1]:.0%}: "
      f"**STIMATO** {reachable_share:.0%}, quindi circa "
      f"**{n_b:.0f} targets real_list**.")
    p()
    p(f"Costo API per saturare la strategia: {n_b:.0f} x ${c_b:.2f} = "
      f"**${n_b*c_b:.2f}**. Tempo di macchina: con 8 ricerche in parallelo, "
      f"circa {n_b/8:.0f}-{n_b/4:.0f} notti.")
    p()
    p("| spesa | ricerche | ottimistico | realistico | pessimistico |")
    p("|---|---|---|---|---|")
    for b in SPEND_LEVELS:
        n = min(b / c_b, n_b)
        note = " *(saturo)*" if b / c_b > n_b else ""
        cells = [fmt(n * SCENARIOS["B"][sc][0])
                 for sc in ("ottimistico", "realistico", "pessimistico")]
        p(f"| ${b} | {fmt(n)}{note} | {cells[0]} | {cells[1]} | {cells[2]} |")
    p()
    for sc in ("ottimistico", "realistico", "pessimistico"):
        prob, reason = SCENARIOS["B"][sc]
        p(f"- **{sc}: p = {prob:.2%}** per ricerca — STIMATO. {reason}.")
    p()
    p("La strategia B e' **satura a meno di two dollari di API**. Tutta la "
      "colonna della spesa, da $50 a $5000, non cambia niente: quello che manca "
      "non sono i soldi, sono i problems con one frontier raggiungibile. "
      "E un eventuale ritrovamento, second il protocollo della fase 7, e' piu' "
      "probabilmente one formalizzazione sbagliata che un result new_item.")
    p()

    # ------------------------------------------------- C
    p("### Strategia C — strategia mista: setaccio, poi affondo mirato")
    p()
    p(f"Si da' **un colpo only** (${c_s:.4f}) a how_many piu' problems possibile, "
      f"fino a coprire all_items i {n_targets}; con quello che resta si comprano "
      f"affondi da ${c_a:.2f}, partendo dai problems dove il colpo only ha "
      f"mostrato un piano sensato. Il first {DIVE_SHARE:.0%} degli affondi "
      f"gode dell'amplificazione (sono i selezionati), il resto vale come A.")
    p()
    p("| spesa | setacciati | affondi | ottimistico | realistico | pessimistico |")
    p("|---|---|---|---|---|---|")
    for b in SPEND_LEVELS:
        n_scr = min(n_targets, b / c_it1)
        resto = max(0.0, b - n_scr * c_it1)
        n_dive = min(n_scr, resto / c_fall)
        cells = []
        for sc in ("ottimistico", "realistico", "pessimistico"):
            p_a = SCENARIOS["A"][sc][0]
            m = AMPLIFICATION[sc]
            head = min(n_dive, DIVE_SHARE * n_scr)
            queue = n_dive - head
            expected = n_scr * FIRST_SHOT_SHARE * p_a + head * m * p_a + queue * p_a
            cells.append(fmt(expected))
        p(f"| ${b} | {fmt(n_scr)} | {fmt(n_dive)} | "
          f"{cells[0]} | {cells[1]} | {cells[2]} |")
    p()
    p(f"- il colpo only cattura la quota **{FIRST_SHOT_SHARE:.0%}** dei successi "
      f"che l'affondo otterrebbe — **MISURATO**: 2 dei 9 successi della "
      f"calibrazione sono arrivati alla before iteration;")
    p(f"- gli affondi selezionati valgono {AMPLIFICATION['ottimistico']:.0f}x / "
      f"{AMPLIFICATION['realistico']:.0f}x / "
      f"{AMPLIFICATION['pessimistico']:.0f}x un affondo alla cieca — "
      f"**STIMATO**: il colpo only scarta i problems su cui il model non ha "
      f"nemmeno un piano; nella calibrazione entrambi i fallimenti avevano un "
      f"piano coerente dalla before iteration, quindi il segnale esiste ma e' "
      f"imperfetto.")
    p(f"- **MISURATO** — coprire con un colpo only all_items i {n_targets} open_problems "
      f"verificabili costa **${n_targets*c_s:.0f}**.")
    p()

    p("### Il confronto in one line")
    p()
    p("| scenario | dollari per successo, A | dollari per successo, C | vantaggio di C |")
    p("|---|---|---|---|")
    for sc in ("ottimistico", "realistico", "pessimistico"):
        p_a = SCENARIOS["A"][sc][0]
        m = AMPLIFICATION[sc]
        resa_a = p_a / c_a
        # C al punto di equilibrio: setaccio su all_items + affondo sul 10%
        costo_c = n_targets * c_s + DIVE_SHARE * n_targets * c_a
        succ_c = (n_targets * FIRST_SHOT_SHARE * p_a
                  + DIVE_SHARE * n_targets * m * p_a)
        resa_c = succ_c / costo_c
        p(f"| {sc} | ${fmt(1/resa_a)} | ${fmt(1/resa_c)} | "
          f"{resa_c/resa_a:.1f}x |")
    p()
    p(f"Il punto di equilibrio della strategia C — un colpo only su all_items i "
      f"{n_targets} open_problems, piu' un affondo sul {DIVE_SHARE:.0%} best — "
      f"costa **${n_targets*c_s + DIVE_SHARE*n_targets*c_a:.0f}**. E' la "
      f"cifra da ricordare: e' il prezzo di one passata complete sull'archive.")
    p()
    return r

def report_part_three(data: dict, r: list[str]) -> list[str]:
    def p(s: str = "") -> None:
        r.append(s)

    idx = data["index"]
    problems = data["cal"]["problems"]
    c_fall = st.mean(x["cost"] for x in problems if not x["solved"])
    c_it1 = st.median(x["costo_it1"] for x in problems)
    c_c = c_it1 + DIVE_SHARE * c_fall
    n_targets = idx["main"]["aperti_verificabili"]

    # ---------------------------------------------------------------- 5
    p("## 5. Il computation local, misurato")
    p()
    p("La strategia B non si paga in dollari ma in tempo di macchina, quindi il "
      "number che count e' la velocita'.")
    p()
    p("| ricerca | che cosa search_for | conclusiva? | candidates examined | findings |")
    p("|---|---|---|---|---|")
    by_name = {v["name"]: v for v in data["hunt"]}
    for name, (cosa, conclusiva, found) in HUNT.items():
        v = by_name.get(name, {})
        st_ = v.get("state") or v.get("result") or {}
        es = st_.get("examined")
        p(f"| `{name}` | {cosa} | {conclusiva} | "
          f"{es if es is not None else '—'} | **{found}** |")
    p()
    reg = ROOT / "runs/hunt/euclide_squarefree/search.log"
    if reg.is_file():
        last = None
        for line in reg.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("{") and "progress" in line:
                try:
                    last = json.loads(line)
                except ValueError:
                    pass
        if last and last.get("seconds"):
            v = last["examined"] / last["seconds"]
            def sp(x) -> str:
                return f"{x:,}".replace(",", " ")
            p(f"**MISURATO** — la ricerca sui numbers di Euclide ha esaminato "
              f"{sp(last['examined'])} primes in {sp(last['seconds'])} "
              f"seconds, cioe' **{v:.0f} candidates al second** su un core, ed "
              f"e' arrivata al first {sp(last.get('current_prime', 0))} senza "
              f"trovare niente: per ognuno di quei primes sono stati controllati "
              f"TUTTI i primoriali con fattori minori, quindi il controllo e' "
              f"full, non partial. Con 8 ricerche in parallelo e 8 hours di "
              f"notte sono circa {v*8*3600/1e6:.1f} milioni di candidates per "
              f"ricerca per notte (**STIMATO**: velocita' misurata per il tempo).")
    p()
    p("**MISURATO** — one check Lean complete costa 32,9 s con sandbox e "
      "fingerprint, 25,0 s senza. Con 4 checks in parallelo sono circa 440 "
      "checks all'now: e' questo, non l'API, il limit di how_many trials si "
      "possono controllare in un giorno.")
    p()
    probe = data["probe"]
    if probe:
        # Stessa rule di scripts/probe_lean.py: `plausible` che non trova
        # counterexamples lascia un `sorry` e il file compila comunque, quindi non
        # e' one closure.
        def notable(v: dict) -> bool:
            for pr in v["trials"]:
                if pr["result"] not in ("closed", "counterexample"):
                    continue
                m = pr.get("messages") or ""
                if ("declaration uses 'sorry'" in m
                        or "Unable to find a counter-example" in m):
                    continue
                return True
            return False

        notable = [v for v in probe if notable(v)]
        n = len(probe)
        low, high = clopper_pearson(len(notable), n)
        p(f"**MISURATO** — probe automatica su {n} enunciati open_problems discreti "
          f"(`decide`, `plausible`, `norm_num`, `simp_arith`, forma diritta e "
          f"negata, {8*n} trials in tutto): **{len(notable)}** hanno prodotto "
          f"qualcosa di notable. Intervallo di Clopper-Pearson al 90% sulla "
          f"frazione di open_problems che cadono da soli: {low:.1%} – {high:.1%}.")
        for v in notable:
            p(f"  - `{v['problem']}`: {v.get('ATTENZIONE', 'da esaminare')}")
        if not notable:
            p("  Nessuno. Un caso apparente — `Arxiv.«2107.12475».CollatzLike` — "
              "era `plausible` che scriveva \"Unable to find a counter-example\" "
              "e lasciava un `sorry`: il file compilava, ma non dimostrava niente. "
              "La rule di verdict e' stata corretta (`scripts/probe_lean.py`).")
    else:
        p("**In corso** — la probe automatica su 30 enunciati open_problems discreti non "
          "e' ancora finita; quando finisce, il suo result aggiorna il limit "
          "superiore usato nello scenario ottimistico della strategia A.")
    p()

    # ---------------------------------------------------------------- 6
    p("## 6. Che cosa NON si puo' stimare")
    p()
    p("1. **La probabilita' che un problem aperto sia risolvibile da questo "
      "system.** E' il number che decide tutto, ed e' esattamente quello che "
      "non ho. Non esiste alcun sample di problems open_problems solved su cui "
      "misurarla: se esistesse, quei problems non sarebbero open_problems. I three "
      "scenari del punto 4 sono ipotesi mie, non misure.")
    p()
    p("2. **Perche' calibrare su problems solved e' ottimistico.** Un problem "
      "con la dimostrazione in archive ha, per construction, one dimostrazione "
      "corta: le undici che ho usato vanno da 1 a 34 lines. Chi ha scritto "
      "l'statement sapeva gia' che si chiudeva, e lo ha formalizzato in way "
      "che si chiudesse. Su un aperto non c'e' nessuna garanzia che esista one "
      "dimostrazione corta, ne' che l'statement sia formulato in one forma "
      "aggredibile. Il 71% misurato (5 su 7) e' il rate su one popolazione "
      "che NON contiene nessun problem aperto.")
    p()
    p("3. **La memorizzazione.** Ho chosen problems entrati nell'archive after il "
      "cut di addestramento dichiarato, ma il cut riguarda l'archive, non "
      "la matematica: la quaterna di Fermat e il counterexample di 17 vertici sono "
      "in letteratura da decenni. Quanta parte dei 9 successi sia ricostruzione e "
      "quanta ricordo, non lo so misurare.")
    p()
    p("4. **Quanto pesa il limit di iterations.** Uno dei two fallimenti si e' "
      "fermato per esaurimento delle 20 iterations, non per incapacita': con 60 "
      "iterations forse si chiudeva. Non l'ho provato, quindi non lo conto.")
    p()
    p("5. **Il value di un ritrovamento.** Se one ricerca trova un counterexample, "
      "il protocollo in `docs/04-protocollo-findings.md` prevede three results: "
      "formalizzazione errata, result gia' noto, candidato new_item. Con zero "
      "findings finora non ho alcun dato su come si dividano, e il caso piu' "
      "probabile a priori e' il first.")
    p()

    # ---------------------------------------------------------------- 7
    p("## 7. Raccomandazione")
    p()
    p(f"**La strategia mista (C), e below i ${1.0*c_c*n_targets:,.0f} non c'e' "
      f"reason di fare other.** Tre ragioni, in order di weight.")
    p()
    p(f"1. *Il setaccio costa quasi niente e copre tutto.* Un colpo only su un "
      f"problem costa ${c_it1:.4f} **MISURATO**. Con **$50** si danno "
      f"{50/c_it1:.0f} shots singoli: piu' dei {n_targets} open_problems verificabili "
      f"dell'archive. Cioe' con cinquanta dollari si trial one volta OGNI "
      f"problem aperto della raccolta, e si scopre dove il model ha un piano "
      f"e dove no. Nessuna altra spesa in questo progetto ha un report "
      f"informazione/prezzo simile.")
    p()
    # vantaggio della strategia mista, scenario realistico
    m = AMPLIFICATION["realistico"]
    resa_a = 1.0 / c_fall
    resa_c = (FIRST_SHOT_SHARE + DIVE_SHARE * m) / (c_it1 + DIVE_SHARE * c_fall)
    p(f"2. *L'affondo va comprato after, non before.* Un affondo costa "
      f"${c_fall:.2f} **MISURATO** e finisce non solved quasi sempre. "
      f"Comprarne one per ognuno dei {n_targets} open_problems costa "
      f"${fmt(n_targets*c_fall)} ed e' il way worst di spendere. Setacciare "
      f"all_items e affondare sui {int(DIVE_SHARE*n_targets)} best_list costa "
      f"${fmt(n_targets*(c_it1 + DIVE_SHARE*c_fall))} e, nello scenario "
      f"realistico, rende **{resa_c/resa_a:.1f} volte** i successi per dollaro "
      f"della strategia A.")
    p()
    p("3. *Il computation local e' gratis: va saturato sempre.* La caccia ai "
      "counterexamples non consuma budget API, only notti di macchina. Va tenuta "
      "accesa in parallelo a qualunque strategia, perche' il suo cost "
      "marginale in dollari e' zero. Ma va puntata sui pochi problems dove i "
      "bounds pubblicati sono bassi: dove la letteratura e' arrivata a 10^22, "
      "nessuna notte di computation cambia niente.")
    p()
    p("**Da which level di spesa ha senso tentare gli open_problems.**")
    p()
    def attesi_c(b: float, scen: str) -> float:
        """Successi expected dalla strategia C, con i tetti del punto 4."""
        p_a = SCENARIOS["A"][scen][0]
        m = AMPLIFICATION[scen]
        n_scr = min(n_targets, b / c_it1)
        resto = max(0.0, b - n_scr * c_it1)
        n_dive = min(n_scr, resto / c_fall)
        head = min(n_dive, DIVE_SHARE * n_scr)
        return (n_scr * FIRST_SHOT_SHARE * p_a + head * m * p_a
                + (n_dive - head) * p_a)

    def terna(b: float) -> str:
        return " / ".join(fmt(attesi_c(b, sc)) for sc in
                          ("ottimistico", "realistico", "pessimistico"))

    p(f"- **$53** — il setaccio full: un colpo only su all_items i "
      f"{n_targets} open_problems verificabili. Successi expected {terna(53)} "
      f"(ottimistico / realistico / pessimistico). Ha senso comunque, also "
      f"aspettandosi zero successi: quello che si compra e' la mapping di dove "
      f"il model ha un piano.")
    p(f"- **$174** — setaccio full piu' affondo sul {DIVE_SHARE:.0%} "
      f"best. Successi expected {terna(174)}. E' il punto in cui, se "
      f"lo scenario realistico e' giusto, un successo diventa probabile piu' "
      f"che no. Sotto questa cifra non c'e' reason di fare other; above, si "
      f"sta scommettendo su un number che nessuno conosce.")
    p(f"- **$500** — successi expected {terna(500)}. Vale la pena only se il "
      f"setaccio da $53 ha mostrato targets promettenti: spent alla cieca, "
      f"paga affondi su problems dove il model non aveva nemmeno un piano.")
    p(f"- **$1000–$5000** — successi expected {terna(1000)} e {terna(5000)}. "
      f"Oltre la saturazione il conto perde significato: comprerebbe seconds e "
      f"terzi attempts sugli stessi problems, e il model li tratta come "
      f"indipendenti dai primes, cosa che non sono. Non lo consiglio senza aver "
      f"before letto i data del setaccio.")
    p()
    p("Si noti l'ampiezza: a ogni level di spesa i three scenari stanno in un "
      "intervallo di two ordini di grandezza. **L'incertezza non e' nel conto: "
      "e' tutta nel value di p**, che il punto 6 dichiara non stimabile. "
      "Chiunque dia un number only, qui, sta indovinando.")
    p()
    p("**Una raccomandazione sui targets, non only sulla spesa.** I "
      f"{idx['main']['risolti_senza_prova']} problems marcati `research solved` "
      f"ma privi di dimostrazione in archive sono one classe intermedia: la "
      f"matematica e' note, manca la formalizzazione. Su quelli il rate di "
      f"successo misurabile sarebbe VERO (si puo' controllare l'result), il "
      f"result e' utile all'archive, e il risk di spendere per niente e' "
      f"molto piu' low. Se l'goal e' 'fare job matematico utile con "
      f"questo system' invece di 'risolvere un problem aperto', quella e' la "
      f"strada con il miglior report tra cost e result — e la calibrazione "
      f"che ho in mano la descrive meglio di quanto descriva gli open_problems.")
    p()
    return r


def main() -> int:
    data = load()
    r = report_text(data)
    r = report_part_two(data, r)
    r = report_part_three(data, r)
    text = "\n".join(r) + "\n"
    output = ROOT / "docs/06-model-costs.md"
    output.write_text(text, encoding="utf-8")
    print(text)
    print(f"(scritto in {output})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
