"""
FASE C — modello dei costi e proiezione sui problemi aperti.

Ogni numero stampato porta un'etichetta:

  MISURATO   viene da un'esecuzione registrata su file in questo repository.
  STIMATO    e' un'ipotesi. Accanto c'e' sempre il ragionamento che la regge.

Il modello non usa librerie esterne: l'intervallo di confidenza e' quello di
Clopper-Pearson, calcolato per bisezione sulla somma binomiale esatta, cosi'
non serve scipy e il conto e' riproducibile da chiunque legga il codice.

Uso:  python3 scripts/modello_costi.py > runs/fase_c.txt
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
from index import ProblemIndex   # noqa: E402

LIVELLI = ("facile", "medio", "difficile")
LIVELLI_SPESA = (50, 100, 200, 500, 1000, 5000)


# ---------------------------------------------------------------- statistica
def _binom_coda_alta(k: int, n: int, p: float) -> float:
    """P(X >= k) per X ~ Binomiale(n, p). Somma esatta, nessuna libreria."""
    return sum(math.comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k, n + 1))


def _binom_coda_bassa(k: int, n: int, p: float) -> float:
    """P(X <= k)."""
    return sum(math.comb(n, i) * p**i * (1 - p)**(n - i) for i in range(0, k + 1))


def _bisezione(f, bersaglio: float, lo: float, hi: float) -> float:
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < bersaglio:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, confidenza: float = 0.90) -> tuple[float, float]:
    """Intervallo di Clopper-Pearson per una proporzione k/n.

    E' l'intervallo che non assume niente sulla forma della distribuzione:
    con numeri piccoli resta largo, ed e' giusto che resti largo.
    """
    alfa = 1 - confidenza
    basso = 0.0 if k == 0 else _bisezione(
        lambda p: _binom_coda_alta(k, n, p), alfa / 2, 0.0, 1.0)
    alto = 1.0 if k == n else _bisezione(
        lambda p: 1 - _binom_coda_bassa(k, n, p), 1 - alfa / 2, 0.0, 1.0)
    return basso, alto


# ---------------------------------------------------------------- dati
def carica() -> dict:
    dati = {}
    dati["cal"] = json.loads(
        (RADICE / "docs/dati/calibrazione_completa.json").read_text(encoding="utf-8"))

    idx = {}
    for nome, perc in (("bench-v1", "verifier/problem_index.json"),
                       ("main", "verifier/problem_index_main.json")):
        i = ProblemIndex.load(RADICE / perc)
        aperti = i.find(category="research open")
        ap_ver = [p for p in aperti if not p.statement_has_sorry]
        ris = i.find(category="research solved")
        idx[nome] = {
            "teoremi": len(i.problems),
            "aperti": len(aperti),
            "aperti_verificabili": len(ap_ver),
            "aperti_con_buco_non_prop": len(aperti) - len(ap_ver),
            "aperti_confutabili": len([p for p in aperti
                                       if p.answer_placeholder_in_source
                                       and not p.statement_has_sorry]),
            "aperti_varianti": len([p for p in ap_ver if ".variants." in p.theorem]),
            "risolti": len(ris),
            "risolti_con_prova_pulita": len([p for p in ris if p.archive_proof_is_clean]),
            "risolti_senza_prova": len([p for p in ris if not p.proof_is_complete
                                        and not p.statement_has_sorry]),
            "prove_complete": len([p for p in i.problems if p.proof_is_complete]),
            "prove_pulite": len([p for p in i.problems if p.archive_proof_is_clean]),
        }
    dati["indice"] = idx

    # prima la copia versionata in docs/dati, cosi' la relazione si rigenera
    # anche su un computer dove runs/ non c'e' (runs/ non e' sotto git)
    sonda = next((p for p in (RADICE / "docs/dati/sonda_lean.json",
                              RADICE / "runs/caccia/sonda_lean.json") if p.is_file()),
                 None)
    dati["sonda"] = json.loads(sonda.read_text(encoding="utf-8")) if sonda else None

    caccia = []
    for cart in sorted((RADICE / "runs/caccia").glob("*/")):
        f = cart / "stato.json"
        g = cart / "esito.json"
        voce = {"nome": cart.name}
        for chiave, percorso in (("stato", f), ("esito", g)):
            if percorso.is_file():
                voce[chiave] = json.loads(percorso.read_text(encoding="utf-8"))
        if len(voce) > 1:
            caccia.append(voce)
    dati["caccia"] = caccia
    return dati


# ---------------------------------------------------------------- modello
def per_livello(problemi: list[dict]) -> dict:
    fuori = {}
    for liv in LIVELLI:
        gruppo = [p for p in problemi if p["livello"] == liv]
        if not gruppo:
            continue
        risolti = [p for p in gruppo if p["risolto"]]
        falliti = [p for p in gruppo if not p["risolto"]]
        basso, alto = clopper_pearson(len(risolti), len(gruppo))
        fuori[liv] = {
            "n": len(gruppo), "risolti": len(risolti),
            "tasso": len(risolti) / len(gruppo),
            "intervallo": (basso, alto),
            "costo_successo": [p["costo"] for p in risolti],
            "costo_fallimento": [p["costo"] for p in falliti],
            "iterazioni_successo": [p["iterazioni"] for p in risolti],
            "secondi": [p["secondi"] for p in gruppo],
        }
    return fuori


def costo_per_successo(p: float, c_successo: float, c_fallimento: float) -> float:
    """Costo atteso per ottenere UN successo, con tentativi indipendenti."""
    if p <= 0:
        return float("inf")
    return (c_successo * p + c_fallimento * (1 - p)) / p


def tabella_proiezione(nome: str, c_tentativo: float, p: float) -> list[tuple]:
    righe = []
    for b in LIVELLI_SPESA:
        n = b / c_tentativo
        righe.append((b, n, n * p))
    return righe


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
# Questi sono gli UNICI numeri inventati del modello. Ognuno porta la sua
# motivazione, e la motivazione dice su quale misura si appoggia.

SCENARI = {
    "A": {
        "nome": "dimostrazioni Lean dirette su enunciati aperti",
        "ottimistico": (0.02,
            "la sonda automatica non ha chiuso nessuno dei 30 enunciati aperti "
            "provati (240 prove): il limite superiore misurato al 90% e' 9,5%. "
            "Prendo circa un quinto di quel tetto, perche' la sonda prova "
            "tattiche mentre l'agente ragiona — quindi puo' fare meglio — ma "
            "9,5% e' il tetto di un campione di 30, non una stima"),
        "realistico": (0.003,
            "un successo ogni ~300 tentativi: la calibrazione misura 5/7 su "
            "varianti GIA' dimostrate in archivio (prove di 10-34 righe), ma "
            "nessun aperto ha una prova corta nota, per definizione di aperto"),
        "pessimistico": (0.0002,
            "un successo ogni 5000: l'archivio e' curato da DeepMind per "
            "raccogliere problemi su cui gli esperti si sono fermati"),
    },
    "B": {
        "nome": "ricerca di controesempi con calcolo locale",
        "ottimistico": (0.05,
            "una minoranza di congetture ha limiti verificati bassi (per la "
            "congettura di Selfridge la letteratura si ferma a k~29): su quelle "
            "il calcolo locale arriva davvero oltre il noto"),
        "realistico": (0.01,
            "misurato in questo progetto: 0 ritrovamenti su 3 ricerche e "
            "~2 ore-CPU; la ricerca sui numeri di Euclide ha superato 2,5 "
            "milioni di primi senza niente"),
        "pessimistico": (0.001,
            "i limiti pubblicati sono quasi sempre fuori portata: per il "
            "problema di Erdos 366 la verifica arriva a 10^22"),
    },
    "C": {
        "nome": "strategia mista: setaccio a basso costo, poi affondo",
        "ottimistico": (None, "derivato da A e B"),
        "realistico": (None, "derivato da A e B"),
        "pessimistico": (None, "derivato da A e B"),
    },
}


# Parametri della strategia mista. Sono tre numeri, dichiarati qui.
QUOTA_AFFONDO = 0.10       # STIMATO: su 10 problemi setacciati, 1 merita l'affondo
AMPLIFICAZIONE = {"ottimistico": 3.0, "realistico": 2.0, "pessimistico": 1.0}
QUOTA_PRIMO_COLPO = 0.22   # MISURATO: 2 dei 9 successi sono arrivati alla prima
                           # iterazione (Wilson, ClaudesCycles)

# Strategia B: quanti bersagli esistono davvero.
N_SELEZIONATI_CACCIA = 30          # MISURATO: runs/caccia/selezione.json
FRAZIONE_FRONTIERA_RAGGIUNGIBILE = 0.50   # STIMATO su 2 letterature su 4 controllate

# Che cosa hanno fatto le ricerche lanciate. I ritrovamenti sono ZERO in tutte e
# tre: la voce `trovati` di erdos396 contiene valori CALCOLATI (il minimo n per
# ogni k), non controesempi, e va letta cosi'.
CACCIA = {
    "euclide_squarefree": (
        "un primo p con p^2 che divide un numero di Euclide",
        "conclusiva: un solo ritrovamento confuterebbe la congettura", 0),
    "erdos409_sigma": (
        "orbite di n -> sigma(n)-1 che non toccano mai un primo",
        "trova sospetti da esaminare a mano, non confutazioni", 0),
    "erdos396_binomiale": (
        "il minimo n con descFactorial(n,k+1) che divide centralBinom(n)",
        "raccoglie indizi: la forma 'per ogni k esiste n' non e' confutabile "
        "da un calcolo", 0),
}


def relazione(dati: dict) -> str:
    r: list[str] = []
    def p(s: str = "") -> None:
        r.append(s)

    cal = dati["cal"]
    problemi = cal["problemi"]
    idx = dati["indice"]
    liv = per_livello(problemi)

    risolti = [x for x in problemi if x["risolto"]]
    falliti = [x for x in problemi if not x["risolto"]]
    c_succ = st.mean(x["costo"] for x in risolti)
    c_fall = st.mean(x["costo"] for x in falliti)
    c_it1 = st.median(x["costo_it1"] for x in problemi)

    p("# Fase C — modello dei costi e proiezione sui problemi aperti")
    p()
    p(f"Generato da `scripts/modello_costi.py`. Modello **{cal['modello']}**, "
      f"effort **{cal['effort']}**, snapshot `{cal['snapshot']}`.")
    p()

    # ---------------------------------------------------------------- 1
    p("## 1. Che cosa e' stato misurato")
    p()
    p(f"**MISURATO** — {len(problemi)} problemi tentati, {len(risolti)} risolti, "
      f"spesa totale ${cal['spesa_totale']:.4f}. Tutti entrati nell'archivio "
      f"dopo il taglio di addestramento dichiarato ({cal['taglio_addestramento']}), "
      f"tutti con la dimostrazione d'archivio accettata dal verificatore, "
      f"tutti con la dimostrazione nascosta all'agente.")
    p()
    p("| livello | righe di prova | esito | iter. | espl. | verifiche | secondi | costo |")
    p("|---|---|---|---|---|---|---|---|")
    for x in problemi:
        p(f"| {x['livello']} | {x['righe_prova']} | "
          f"{'**risolto**' if x['risolto'] else 'non risolto'} | "
          f"{x['iterazioni']} | {x['esplorazioni']} | {x['verifiche']} | "
          f"{x['secondi']} | ${x['costo']:.4f} |")
    p()

    # ---------------------------------------------------------------- 2
    p("## 2. Il modello, livello per livello")
    p()
    p("Il tasso di successo e' accompagnato dall'intervallo di Clopper-Pearson "
      "al 90%: con quattro o cinque problemi per livello l'intervallo e' larghissimo, "
      "e dichiararlo e' l'unico modo onesto di dare il numero.")
    p()
    p("| livello | n | risolti | tasso | intervallo 90% | costo medio se risolto | costo se fallito |")
    p("|---|---|---|---|---|---|---|")
    for nome, v in liv.items():
        cs = f"${st.mean(v['costo_successo']):.4f}" if v["costo_successo"] else "—"
        cf = (f"${st.mean(v['costo_fallimento']):.4f}" if v["costo_fallimento"] else "—")
        p(f"| {nome} | {v['n']} | {v['risolti']} | {v['tasso']:.0%} | "
          f"{v['intervallo'][0]:.0%} – {v['intervallo'][1]:.0%} | {cs} | {cf} |")
    tot_b, tot_a = clopper_pearson(len(risolti), len(problemi))
    p(f"| **totale** | {len(problemi)} | {len(risolti)} | "
      f"{len(risolti)/len(problemi):.0%} | {tot_b:.0%} – {tot_a:.0%} | "
      f"${c_succ:.4f} | ${c_fall:.4f} |")
    p()
    p("**MISURATO** — le quattro voci di livello `facile` sono problemi di "
      "categoria `test`, cioe' controlli di sanita' scritti dagli autori "
      "dell'archivio: 4 su 4. Le sette voci `medio` e `difficile` sono varianti "
      "di congetture vere e proprie, di categoria `research solved`: 5 su 7. "
      "Il numero da ricordare e' **5 su 7**, non 9 su 11.")
    p()
    p(f"**MISURATO** — costo medio di un successo ${c_succ:.4f}; "
      f"costo medio di un fallimento ${c_fall:.4f}. Un fallimento costa "
      f"{c_fall/c_succ:.0f} volte un successo, perche' il fallimento consuma "
      f"tutto il tetto per problema mentre il successo si ferma appena la "
      f"dimostrazione passa.")
    p()
    p(f"**MISURATO** — costo della PRIMA iterazione, mediana su {len(problemi)} "
      f"problemi: ${c_it1:.4f}. Due dei nove successi sono arrivati proprio alla "
      f"prima iterazione. Questo e' il prezzo di un colpo solo, e serve alla "
      f"strategia mista del punto 4.")
    p()
    ore_lean = sum(x["secondi_lean"] for x in problemi) / 3600
    ore_tot = sum(x["secondi"] for x in problemi) / 3600
    p(f"**MISURATO** — tempo di calendario: {ore_tot:.2f} ore in tutto, di cui "
      f"{ore_lean:.2f} ore di Lean in locale ({100*ore_lean/ore_tot:.0f}%). "
      f"Il collo di bottiglia non e' l'API: e' il verificatore.")
    p()
    p("### Costo per problema risolto")
    p()
    p("Formula: (costo se risolto x p + costo se fallito x (1-p)) / p, cioe' quanto "
      "costa in media arrivare a UN successo ritentando su problemi diversi.")
    p()
    p("| livello | p | costo per successo | con p al minimo dell'intervallo | al massimo |")
    p("|---|---|---|---|---|")
    for nome, v in liv.items():
        cs = st.mean(v["costo_successo"]) if v["costo_successo"] else c_succ
        cf = st.mean(v["costo_fallimento"]) if v["costo_fallimento"] else c_fall
        a = costo_per_successo(v["tasso"], cs, cf)
        b = costo_per_successo(v["intervallo"][0], cs, cf)
        c = costo_per_successo(v["intervallo"][1], cs, cf)
        p(f"| {nome} | {v['tasso']:.0%} | ${fmt(a)} | ${fmt(b)} | ${fmt(c)} |")
    p()
    return r

def relazione_seconda_parte(dati: dict, r: list[str]) -> list[str]:
    def p(s: str = "") -> None:
        r.append(s)

    cal = dati["cal"]
    problemi = cal["problemi"]
    idx = dati["indice"]
    risolti = [x for x in problemi if x["risolto"]]
    falliti = [x for x in problemi if not x["risolto"]]
    c_succ = st.mean(x["costo"] for x in risolti)
    c_fall = st.mean(x["costo"] for x in falliti)
    c_it1 = st.median(x["costo_it1"] for x in problemi)

    # ---------------------------------------------------------------- 3
    p("## 3. Quanti bersagli ci sono")
    p()
    p("| | bench-v1 | main (0a8b856c) |")
    p("|---|---|---|")
    voci = [
        ("teoremi indicizzati", "teoremi"),
        ("`research open`", "aperti"),
        ("aperti con enunciato completo (verificabili)", "aperti_verificabili"),
        ("aperti con buco `answer( )` non proposizionale", "aperti_con_buco_non_prop"),
        ("aperti attaccabili per confutazione", "aperti_confutabili"),
        ("aperti che sono varianti ausiliarie", "aperti_varianti"),
        ("`research solved`", "risolti"),
        ("risolti con dimostrazione pulita in archivio", "risolti_con_prova_pulita"),
        ("risolti SENZA dimostrazione in archivio", "risolti_senza_prova"),
    ]
    for etichetta, chiave in voci:
        p(f"| {etichetta} | {idx['bench-v1'][chiave]} | {idx['main'][chiave]} |")
    p()
    p("Tutti **MISURATI** sull'indice costruito da Lean.")
    p()
    p("I conteggi di `main` valgono con la semantica `google.answer = "
      "always_true`, quella predefinita, in cui `answer(sorry) ↔ P` diventa "
      "`True ↔ P` e il problema e' davvero dimostrabile. Fino a questa sessione "
      "lo snapshot dichiarava anche una seconda libreria che compilava gli "
      "stessi file con `postpone`, e i due insiemi di `.olean` si sovrascrivevano "
      "a vicenda: con quella semantica gli stessi 94 problemi non sono "
      "attaccabili affatto. La libreria in eccesso e' stata disattivata — vedi "
      "`docs/01` — e i numeri qui sopra sono quelli della semantica giusta.")
    p()
    p(f"Due osservazioni che cambiano la strategia. Primo: **nessuno** dei "
      f"{idx['main']['aperti']} problemi marcati `research open` ha una "
      f"dimostrazione completa in archivio — l'archivio e' coerente con se stesso, "
      f"non ci sono aperti 'per distrazione' da raccogliere. Secondo: "
      f"{idx['main']['risolti_senza_prova']} problemi sono marcati `research solved` "
      f"ma non hanno alcuna dimostrazione Lean in archivio: la matematica e' nota, "
      f"la formalizzazione manca. Quella e' una terza classe di bersagli, piu' "
      f"facile degli aperti e piu' difficile di quelli su cui ho calibrato.")
    p()

    # ---------------------------------------------------------------- 4
    p("## 4. Proiezione sui problemi aperti")
    p()
    p("Le probabilita' di successo su un problema **aperto** non sono misurabili: "
      "sono le tre ipotesi qui sotto, e ogni riga dichiara su cosa si appoggia. "
      "I conti tengono conto del fatto che i bersagli sono in numero **finito**: "
      "quando una strategia li ha esauriti, la spesa in piu' non compra niente "
      "che questo modello sappia valutare.")
    p()
    n_bersagli = idx["main"]["aperti_verificabili"]
    c_a = c_fall
    c_s = c_it1
    c_b = 0.10

    p("### Costo di un tentativo (base del conto)")
    p()
    p(f"- **A, affondo completo** su un enunciato aperto: **${c_a:.2f}** — "
      f"**MISURATO**, media dei due fallimenti della calibrazione "
      f"(${falliti[0]['costo']:.4f} fermato dalle 20 iterazioni, "
      f"${falliti[1]['costo']:.4f} fermato dal tetto di spesa). Su un aperto il "
      f"tentativo finisce quasi sempre cosi'.")
    p(f"- **C, colpo solo** (setaccio): **${c_s:.4f}** — **MISURATO**, mediana "
      f"del costo della prima iterazione sugli 11 problemi della calibrazione.")
    p(f"- **B, programma di ricerca** scritto e lanciato: **${c_b:.2f}** di API "
      f"per problema — **STIMATO**, dell'ordine del costo misurato dei problemi "
      f"facili (media "
      f"${st.mean(x['costo'] for x in problemi if x['livello']=='facile'):.4f}). "
      f"Il calcolo locale non costa dollari: costa notti di macchina.")
    p()

    # ------------------------------------------------- A
    p("### Strategia A — dimostrazioni Lean dirette su enunciati aperti")
    p()
    p(f"Un affondo per problema, scelti a caso tra i {n_bersagli} aperti "
      f"verificabili. Saturazione a **${fmt(n_bersagli*c_a)}**.")
    p()
    p("| spesa | affondi | ottimistico | realistico | pessimistico |")
    p("|---|---|---|---|---|")
    for b in LIVELLI_SPESA:
        n = min(b / c_a, n_bersagli)
        nota = " *(saturo)*" if b / c_a > n_bersagli else ""
        celle = [fmt(n * SCENARI["A"][sc][0])
                 for sc in ("ottimistico", "realistico", "pessimistico")]
        p(f"| ${b} | {fmt(n)}{nota} | {celle[0]} | {celle[1]} | {celle[2]} |")
    p()
    for sc in ("ottimistico", "realistico", "pessimistico"):
        prob, motivo = SCENARI["A"][sc]
        p(f"- **{sc}: p = {prob:.2%}** — STIMATO. {motivo}.")
    p()

    # ------------------------------------------------- B
    idonei_totali = N_SELEZIONATI_CACCIA
    quota_raggiungibili = FRAZIONE_FRONTIERA_RAGGIUNGIBILE
    n_b = idonei_totali * quota_raggiungibili
    p("### Strategia B — ricerca di controesempi con calcolo locale")
    p()
    p(f"Qui il limite non e' il denaro: e' il numero di problemi su cui una "
      f"ricerca ha senso. **MISURATO**: lo script di selezione ne ha trovati "
      f"{idonei_totali} adatti al calcolo su tutto l'archivio. Dei quattro di cui "
      f"ho controllato la letteratura, due hanno una frontiera raggiungibile "
      f"(numeri di Euclide: nessuna ricerca sistematica pubblicata; congettura di "
      f"Selfridge: verificata solo fino a k circa 29) e due no (Erdos 366: "
      f"verificata fino a 10^22; Goldbach e Legendre: fino a 4x10^18). Due su "
      f"quattro, intervallo di Clopper-Pearson al 90% "
      f"{clopper_pearson(2,4)[0]:.0%} – {clopper_pearson(2,4)[1]:.0%}: "
      f"**STIMATO** {quota_raggiungibili:.0%}, quindi circa "
      f"**{n_b:.0f} bersagli veri**.")
    p()
    p(f"Costo API per saturare la strategia: {n_b:.0f} x ${c_b:.2f} = "
      f"**${n_b*c_b:.2f}**. Tempo di macchina: con 8 ricerche in parallelo, "
      f"circa {n_b/8:.0f}-{n_b/4:.0f} notti.")
    p()
    p("| spesa | ricerche | ottimistico | realistico | pessimistico |")
    p("|---|---|---|---|---|")
    for b in LIVELLI_SPESA:
        n = min(b / c_b, n_b)
        nota = " *(saturo)*" if b / c_b > n_b else ""
        celle = [fmt(n * SCENARI["B"][sc][0])
                 for sc in ("ottimistico", "realistico", "pessimistico")]
        p(f"| ${b} | {fmt(n)}{nota} | {celle[0]} | {celle[1]} | {celle[2]} |")
    p()
    for sc in ("ottimistico", "realistico", "pessimistico"):
        prob, motivo = SCENARI["B"][sc]
        p(f"- **{sc}: p = {prob:.2%}** per ricerca — STIMATO. {motivo}.")
    p()
    p("La strategia B e' **satura a meno di due dollari di API**. Tutta la "
      "colonna della spesa, da $50 a $5000, non cambia niente: quello che manca "
      "non sono i soldi, sono i problemi con una frontiera raggiungibile. "
      "E un eventuale ritrovamento, secondo il protocollo della fase 7, e' piu' "
      "probabilmente una formalizzazione sbagliata che un risultato nuovo.")
    p()

    # ------------------------------------------------- C
    p("### Strategia C — strategia mista: setaccio, poi affondo mirato")
    p()
    p(f"Si da' **un colpo solo** (${c_s:.4f}) a quanti piu' problemi possibile, "
      f"fino a coprire tutti i {n_bersagli}; con quello che resta si comprano "
      f"affondi da ${c_a:.2f}, partendo dai problemi dove il colpo solo ha "
      f"mostrato un piano sensato. Il primo {QUOTA_AFFONDO:.0%} degli affondi "
      f"gode dell'amplificazione (sono i selezionati), il resto vale come A.")
    p()
    p("| spesa | setacciati | affondi | ottimistico | realistico | pessimistico |")
    p("|---|---|---|---|---|---|")
    for b in LIVELLI_SPESA:
        n_scr = min(n_bersagli, b / c_it1)
        resto = max(0.0, b - n_scr * c_it1)
        n_dive = min(n_scr, resto / c_fall)
        celle = []
        for sc in ("ottimistico", "realistico", "pessimistico"):
            p_a = SCENARI["A"][sc][0]
            m = AMPLIFICAZIONE[sc]
            testa = min(n_dive, QUOTA_AFFONDO * n_scr)
            coda = n_dive - testa
            attesi = n_scr * QUOTA_PRIMO_COLPO * p_a + testa * m * p_a + coda * p_a
            celle.append(fmt(attesi))
        p(f"| ${b} | {fmt(n_scr)} | {fmt(n_dive)} | "
          f"{celle[0]} | {celle[1]} | {celle[2]} |")
    p()
    p(f"- il colpo solo cattura la quota **{QUOTA_PRIMO_COLPO:.0%}** dei successi "
      f"che l'affondo otterrebbe — **MISURATO**: 2 dei 9 successi della "
      f"calibrazione sono arrivati alla prima iterazione;")
    p(f"- gli affondi selezionati valgono {AMPLIFICAZIONE['ottimistico']:.0f}x / "
      f"{AMPLIFICAZIONE['realistico']:.0f}x / "
      f"{AMPLIFICAZIONE['pessimistico']:.0f}x un affondo alla cieca — "
      f"**STIMATO**: il colpo solo scarta i problemi su cui il modello non ha "
      f"nemmeno un piano; nella calibrazione entrambi i fallimenti avevano un "
      f"piano coerente dalla prima iterazione, quindi il segnale esiste ma e' "
      f"imperfetto.")
    p(f"- **MISURATO** — coprire con un colpo solo tutti i {n_bersagli} aperti "
      f"verificabili costa **${n_bersagli*c_s:.0f}**.")
    p()

    p("### Il confronto in una riga")
    p()
    p("| scenario | dollari per successo, A | dollari per successo, C | vantaggio di C |")
    p("|---|---|---|---|")
    for sc in ("ottimistico", "realistico", "pessimistico"):
        p_a = SCENARI["A"][sc][0]
        m = AMPLIFICAZIONE[sc]
        resa_a = p_a / c_a
        # C al punto di equilibrio: setaccio su tutti + affondo sul 10%
        costo_c = n_bersagli * c_s + QUOTA_AFFONDO * n_bersagli * c_a
        succ_c = (n_bersagli * QUOTA_PRIMO_COLPO * p_a
                  + QUOTA_AFFONDO * n_bersagli * m * p_a)
        resa_c = succ_c / costo_c
        p(f"| {sc} | ${fmt(1/resa_a)} | ${fmt(1/resa_c)} | "
          f"{resa_c/resa_a:.1f}x |")
    p()
    p(f"Il punto di equilibrio della strategia C — un colpo solo su tutti i "
      f"{n_bersagli} aperti, piu' un affondo sul {QUOTA_AFFONDO:.0%} migliore — "
      f"costa **${n_bersagli*c_s + QUOTA_AFFONDO*n_bersagli*c_a:.0f}**. E' la "
      f"cifra da ricordare: e' il prezzo di una passata completa sull'archivio.")
    p()
    return r

def relazione_terza_parte(dati: dict, r: list[str]) -> list[str]:
    def p(s: str = "") -> None:
        r.append(s)

    idx = dati["indice"]
    problemi = dati["cal"]["problemi"]
    c_fall = st.mean(x["costo"] for x in problemi if not x["risolto"])
    c_it1 = st.median(x["costo_it1"] for x in problemi)
    c_c = c_it1 + QUOTA_AFFONDO * c_fall
    n_bersagli = idx["main"]["aperti_verificabili"]

    # ---------------------------------------------------------------- 5
    p("## 5. Il calcolo locale, misurato")
    p()
    p("La strategia B non si paga in dollari ma in tempo di macchina, quindi il "
      "numero che conta e' la velocita'.")
    p()
    p("| ricerca | che cosa cerca | conclusiva? | candidati esaminati | ritrovamenti |")
    p("|---|---|---|---|---|")
    per_nome = {v["nome"]: v for v in dati["caccia"]}
    for nome, (cosa, conclusiva, trovati) in CACCIA.items():
        v = per_nome.get(nome, {})
        st_ = v.get("stato") or v.get("esito") or {}
        es = st_.get("esaminati")
        p(f"| `{nome}` | {cosa} | {conclusiva} | "
          f"{es if es is not None else '—'} | **{trovati}** |")
    p()
    reg = RADICE / "runs/caccia/euclide_squarefree/ricerca.log"
    if reg.is_file():
        ultimo = None
        for riga in reg.read_text(encoding="utf-8").splitlines():
            riga = riga.strip()
            if riga.startswith("{") and "progresso" in riga:
                try:
                    ultimo = json.loads(riga)
                except ValueError:
                    pass
        if ultimo and ultimo.get("secondi"):
            v = ultimo["esaminati"] / ultimo["secondi"]
            def sp(x) -> str:
                return f"{x:,}".replace(",", " ")
            p(f"**MISURATO** — la ricerca sui numeri di Euclide ha esaminato "
              f"{sp(ultimo['esaminati'])} primi in {sp(ultimo['secondi'])} "
              f"secondi, cioe' **{v:.0f} candidati al secondo** su un core, ed "
              f"e' arrivata al primo {sp(ultimo.get('primo_corrente', 0))} senza "
              f"trovare niente: per ognuno di quei primi sono stati controllati "
              f"TUTTI i primoriali con fattori minori, quindi il controllo e' "
              f"completo, non parziale. Con 8 ricerche in parallelo e 8 ore di "
              f"notte sono circa {v*8*3600/1e6:.1f} milioni di candidati per "
              f"ricerca per notte (**STIMATO**: velocita' misurata per il tempo).")
    p()
    p("**MISURATO** — una verifica Lean completa costa 32,9 s con sandbox e "
      "impronta, 25,0 s senza. Con 4 verifiche in parallelo sono circa 440 "
      "verifiche all'ora: e' questo, non l'API, il limite di quante prove si "
      "possono controllare in un giorno.")
    p()
    sonda = dati["sonda"]
    if sonda:
        # Stessa regola di scripts/sonda_lean.py: `plausible` che non trova
        # controesempi lascia un `sorry` e il file compila comunque, quindi non
        # e' una chiusura.
        def notevole(v: dict) -> bool:
            for pr in v["prove"]:
                if pr["esito"] not in ("chiusa", "controesempio"):
                    continue
                m = pr.get("messaggi") or ""
                if ("declaration uses 'sorry'" in m
                        or "Unable to find a counter-example" in m):
                    continue
                return True
            return False

        notevoli = [v for v in sonda if notevole(v)]
        n = len(sonda)
        basso, alto = clopper_pearson(len(notevoli), n)
        p(f"**MISURATO** — sonda automatica su {n} enunciati aperti discreti "
          f"(`decide`, `plausible`, `norm_num`, `simp_arith`, forma diritta e "
          f"negata, {8*n} prove in tutto): **{len(notevoli)}** hanno prodotto "
          f"qualcosa di notevole. Intervallo di Clopper-Pearson al 90% sulla "
          f"frazione di aperti che cadono da soli: {basso:.1%} – {alto:.1%}.")
        for v in notevoli:
            p(f"  - `{v['problema']}`: {v.get('ATTENZIONE', 'da esaminare')}")
        if not notevoli:
            p("  Nessuno. Un caso apparente — `Arxiv.«2107.12475».CollatzLike` — "
              "era `plausible` che scriveva \"Unable to find a counter-example\" "
              "e lasciava un `sorry`: il file compilava, ma non dimostrava niente. "
              "La regola di verdetto e' stata corretta (`scripts/sonda_lean.py`).")
    else:
        p("**In corso** — la sonda automatica su 30 enunciati aperti discreti non "
          "e' ancora finita; quando finisce, il suo esito aggiorna il limite "
          "superiore usato nello scenario ottimistico della strategia A.")
    p()

    # ---------------------------------------------------------------- 6
    p("## 6. Che cosa NON si puo' stimare")
    p()
    p("1. **La probabilita' che un problema aperto sia risolvibile da questo "
      "sistema.** E' il numero che decide tutto, ed e' esattamente quello che "
      "non ho. Non esiste alcun campione di problemi aperti risolti su cui "
      "misurarla: se esistesse, quei problemi non sarebbero aperti. I tre "
      "scenari del punto 4 sono ipotesi mie, non misure.")
    p()
    p("2. **Perche' calibrare su problemi risolti e' ottimistico.** Un problema "
      "con la dimostrazione in archivio ha, per costruzione, una dimostrazione "
      "corta: le undici che ho usato vanno da 1 a 34 righe. Chi ha scritto "
      "l'enunciato sapeva gia' che si chiudeva, e lo ha formalizzato in modo "
      "che si chiudesse. Su un aperto non c'e' nessuna garanzia che esista una "
      "dimostrazione corta, ne' che l'enunciato sia formulato in una forma "
      "aggredibile. Il 71% misurato (5 su 7) e' il tasso su una popolazione "
      "che NON contiene nessun problema aperto.")
    p()
    p("3. **La memorizzazione.** Ho scelto problemi entrati nell'archivio dopo il "
      "taglio di addestramento dichiarato, ma il taglio riguarda l'archivio, non "
      "la matematica: la quaterna di Fermat e il controesempio di 17 vertici sono "
      "in letteratura da decenni. Quanta parte dei 9 successi sia ricostruzione e "
      "quanta ricordo, non lo so misurare.")
    p()
    p("4. **Quanto pesa il limite di iterazioni.** Uno dei due fallimenti si e' "
      "fermato per esaurimento delle 20 iterazioni, non per incapacita': con 60 "
      "iterazioni forse si chiudeva. Non l'ho provato, quindi non lo conto.")
    p()
    p("5. **Il valore di un ritrovamento.** Se una ricerca trova un controesempio, "
      "il protocollo in `docs/04-protocollo-ritrovamenti.md` prevede tre esiti: "
      "formalizzazione errata, risultato gia' noto, candidato nuovo. Con zero "
      "ritrovamenti finora non ho alcun dato su come si dividano, e il caso piu' "
      "probabile a priori e' il primo.")
    p()

    # ---------------------------------------------------------------- 7
    p("## 7. Raccomandazione")
    p()
    p(f"**La strategia mista (C), e sotto i ${1.0*c_c*n_bersagli:,.0f} non c'e' "
      f"motivo di fare altro.** Tre ragioni, in ordine di peso.")
    p()
    p(f"1. *Il setaccio costa quasi niente e copre tutto.* Un colpo solo su un "
      f"problema costa ${c_it1:.4f} **MISURATO**. Con **$50** si danno "
      f"{50/c_it1:.0f} colpi singoli: piu' dei {n_bersagli} aperti verificabili "
      f"dell'archivio. Cioe' con cinquanta dollari si prova una volta OGNI "
      f"problema aperto della raccolta, e si scopre dove il modello ha un piano "
      f"e dove no. Nessuna altra spesa in questo progetto ha un rapporto "
      f"informazione/prezzo simile.")
    p()
    # vantaggio della strategia mista, scenario realistico
    m = AMPLIFICAZIONE["realistico"]
    resa_a = 1.0 / c_fall
    resa_c = (QUOTA_PRIMO_COLPO + QUOTA_AFFONDO * m) / (c_it1 + QUOTA_AFFONDO * c_fall)
    p(f"2. *L'affondo va comprato dopo, non prima.* Un affondo costa "
      f"${c_fall:.2f} **MISURATO** e finisce non risolto quasi sempre. "
      f"Comprarne uno per ognuno dei {n_bersagli} aperti costa "
      f"${fmt(n_bersagli*c_fall)} ed e' il modo peggiore di spendere. Setacciare "
      f"tutti e affondare sui {int(QUOTA_AFFONDO*n_bersagli)} migliori costa "
      f"${fmt(n_bersagli*(c_it1 + QUOTA_AFFONDO*c_fall))} e, nello scenario "
      f"realistico, rende **{resa_c/resa_a:.1f} volte** i successi per dollaro "
      f"della strategia A.")
    p()
    p("3. *Il calcolo locale e' gratis: va saturato sempre.* La caccia ai "
      "controesempi non consuma budget API, solo notti di macchina. Va tenuta "
      "accesa in parallelo a qualunque strategia, perche' il suo costo "
      "marginale in dollari e' zero. Ma va puntata sui pochi problemi dove i "
      "limiti pubblicati sono bassi: dove la letteratura e' arrivata a 10^22, "
      "nessuna notte di calcolo cambia niente.")
    p()
    p("**Da quale livello di spesa ha senso tentare gli aperti.**")
    p()
    def attesi_c(b: float, scen: str) -> float:
        """Successi attesi dalla strategia C, con i tetti del punto 4."""
        p_a = SCENARI["A"][scen][0]
        m = AMPLIFICAZIONE[scen]
        n_scr = min(n_bersagli, b / c_it1)
        resto = max(0.0, b - n_scr * c_it1)
        n_dive = min(n_scr, resto / c_fall)
        testa = min(n_dive, QUOTA_AFFONDO * n_scr)
        return (n_scr * QUOTA_PRIMO_COLPO * p_a + testa * m * p_a
                + (n_dive - testa) * p_a)

    def terna(b: float) -> str:
        return " / ".join(fmt(attesi_c(b, sc)) for sc in
                          ("ottimistico", "realistico", "pessimistico"))

    p(f"- **$53** — il setaccio completo: un colpo solo su tutti i "
      f"{n_bersagli} aperti verificabili. Successi attesi {terna(53)} "
      f"(ottimistico / realistico / pessimistico). Ha senso comunque, anche "
      f"aspettandosi zero successi: quello che si compra e' la mappa di dove "
      f"il modello ha un piano.")
    p(f"- **$174** — setaccio completo piu' affondo sul {QUOTA_AFFONDO:.0%} "
      f"migliore. Successi attesi {terna(174)}. E' il punto in cui, se "
      f"lo scenario realistico e' giusto, un successo diventa probabile piu' "
      f"che no. Sotto questa cifra non c'e' motivo di fare altro; sopra, si "
      f"sta scommettendo su un numero che nessuno conosce.")
    p(f"- **$500** — successi attesi {terna(500)}. Vale la pena solo se il "
      f"setaccio da $53 ha mostrato bersagli promettenti: speso alla cieca, "
      f"paga affondi su problemi dove il modello non aveva nemmeno un piano.")
    p(f"- **$1000–$5000** — successi attesi {terna(1000)} e {terna(5000)}. "
      f"Oltre la saturazione il conto perde significato: comprerebbe secondi e "
      f"terzi tentativi sugli stessi problemi, e il modello li tratta come "
      f"indipendenti dai primi, cosa che non sono. Non lo consiglio senza aver "
      f"prima letto i dati del setaccio.")
    p()
    p("Si noti l'ampiezza: a ogni livello di spesa i tre scenari stanno in un "
      "intervallo di due ordini di grandezza. **L'incertezza non e' nel conto: "
      "e' tutta nel valore di p**, che il punto 6 dichiara non stimabile. "
      "Chiunque dia un numero solo, qui, sta indovinando.")
    p()
    p("**Una raccomandazione sui bersagli, non solo sulla spesa.** I "
      f"{idx['main']['risolti_senza_prova']} problemi marcati `research solved` "
      f"ma privi di dimostrazione in archivio sono una classe intermedia: la "
      f"matematica e' nota, manca la formalizzazione. Su quelli il tasso di "
      f"successo misurabile sarebbe VERO (si puo' controllare l'esito), il "
      f"risultato e' utile all'archivio, e il rischio di spendere per niente e' "
      f"molto piu' basso. Se l'obiettivo e' 'fare lavoro matematico utile con "
      f"questo sistema' invece di 'risolvere un problema aperto', quella e' la "
      f"strada con il miglior rapporto tra costo e risultato — e la calibrazione "
      f"che ho in mano la descrive meglio di quanto descriva gli aperti.")
    p()
    return r


def main() -> int:
    dati = carica()
    r = relazione(dati)
    r = relazione_seconda_parte(dati, r)
    r = relazione_terza_parte(dati, r)
    testo = "\n".join(r) + "\n"
    uscita = RADICE / "docs/06-modello-costi.md"
    uscita.write_text(testo, encoding="utf-8")
    print(testo)
    print(f"(scritto in {uscita})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
