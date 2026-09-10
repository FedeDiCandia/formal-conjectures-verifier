"""
Caratterizza i problemi APERTI verificabili dell'archivio.

Analisi automatica degli enunciati elaborati da Lean. Ogni criterio e'
dichiarato: dove uso un'euristica lo dico, perche' una forma logica dedotta da
una stringa non e' un dato misurato ma una classificazione approssimata.
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
from index import ProblemIndex

idx = ProblemIndex.load()

aperti = idx.find(category="research open")
verificabili = [p for p in aperti if not p.statement_has_sorry]
non_verificabili = [p for p in aperti if p.statement_has_sorry]

print("=" * 78)
print("PROBLEMI APERTI DELL'ARCHIVIO")
print("=" * 78)
print(f"  totale con categoria `research open`   {len(aperti)}   (MISURATO)")
print(f"  verificabili (enunciato senza buchi)   {len(verificabili)}   (MISURATO)")
print(f"  NON verificabili (buco answer( ) non")
print(f"    proposizionale: chiedono un valore)  {len(non_verificabili)}   (MISURATO)")

# --- forma logica ------------------------------------------------------------
# CLASSIFICAZIONE EURISTICA su stringhe, non un'analisi dell'albero sintattico.
# La regola e' esplicita e verificabile leggendola.

def forma_logica(enunciato: str) -> str:
    e = enunciato.strip()
    prefisso_answer = e.startswith("True ↔") or e.startswith("True  ↔")
    if prefisso_answer:
        corpo = e.split("↔", 1)[1].strip()
    else:
        corpo = e
    inizio = corpo.lstrip("(¬ \n")
    if inizio.startswith("∀"):
        base = "universale (∀ ...)"
    elif inizio.startswith("∃"):
        base = "esistenziale (∃ ...)"
    elif corpo.lstrip().startswith("¬"):
        base = "negazione (¬ ...)"
    elif "↔" in corpo:
        base = "equivalenza (... ↔ ...)"
    elif re.match(r"^[A-Za-z_][\w.']*\s", corpo) and "=" not in corpo.split("\n")[0][:60]:
        base = "predicato applicato"
    elif "=" in corpo:
        base = "uguaglianza"
    else:
        base = "altro"
    return ("answer( ) proposizionale + " + base) if prefisso_answer else base


forme = Counter(forma_logica(p.statement) for p in verificabili)
print("\n" + "-" * 78)
print("FORMA LOGICA (classificazione EURISTICA su stringhe — regola in questo file)")
print("-" * 78)
for f, n in forme.most_common():
    print(f"  {n:5d}  {f}")

# --- area AMS ---------------------------------------------------------------
AMS = {
    "3": "logica e fondamenti", "03": "logica e fondamenti",
    "5": "combinatoria", "05": "combinatoria",
    "6": "ordini e reticoli", "06": "ordini e reticoli",
    "8": "sistemi algebrici", "08": "sistemi algebrici",
    "11": "teoria dei numeri", "12": "campi e polinomi", "13": "algebra commutativa",
    "14": "geometria algebrica", "15": "algebra lineare", "16": "anelli associativi",
    "17": "anelli non associativi", "18": "teoria delle categorie", "19": "K-teoria",
    "20": "teoria dei gruppi", "22": "gruppi topologici e di Lie",
    "26": "funzioni reali", "28": "misura e integrazione", "30": "analisi complessa",
    "31": "teoria del potenziale", "32": "piu' variabili complesse",
    "33": "funzioni speciali", "34": "equazioni differenziali ordinarie",
    "35": "equazioni alle derivate parziali", "37": "sistemi dinamici",
    "39": "equazioni funzionali", "40": "successioni e serie",
    "41": "approssimazioni", "42": "analisi armonica", "43": "analisi armonica astratta",
    "44": "trasformate integrali", "45": "equazioni integrali",
    "46": "analisi funzionale", "47": "teoria degli operatori",
    "49": "calcolo delle variazioni", "51": "geometria",
    "52": "geometria convessa e discreta", "53": "geometria differenziale",
    "54": "topologia generale", "55": "topologia algebrica",
    "57": "varieta' e complessi", "58": "analisi globale",
    "60": "probabilita'", "62": "statistica", "65": "analisi numerica",
    "68": "informatica", "70": "meccanica", "74": "solidi deformabili",
    "76": "meccanica dei fluidi", "78": "ottica ed elettromagnetismo",
    "80": "termodinamica", "81": "teoria quantistica", "82": "meccanica statistica",
    "83": "relativita'", "85": "astronomia", "86": "geofisica",
    "90": "programmazione matematica", "91": "teoria dei giochi",
    "92": "biologia", "93": "teoria dei sistemi e controllo",
    "94": "informazione e codici", "97": "didattica della matematica",
}
aree = Counter()
for p in verificabili:
    for s in (p.subjects or ["(nessuno)"]):
        aree[AMS.get(s, f"AMS {s}")] += 1
print("\n" + "-" * 78)
print("AREA MATEMATICA (MISURATO: dall'attributo AMS; un problema puo' averne piu' di una)")
print("-" * 78)
for a, n in aree.most_common(18):
    print(f"  {n:5d}  {a}")
if len(aree) > 18:
    print(f"  {sum(n for _, n in aree.most_common()[18:]):5d}  (altre {len(aree)-18} aree)")

# --- fonte -------------------------------------------------------------------
def fonte(modulo: str) -> str:
    parti = modulo.split(".")
    return parti[1] if len(parti) > 1 else modulo


fonti = Counter(fonte(p.module) for p in verificabili)
print("\n" + "-" * 78)
print("FONTE (MISURATO: dalla cartella dell'archivio)")
print("-" * 78)
for f, n in fonti.most_common(15):
    print(f"  {n:5d}  {f}")
if len(fonti) > 15:
    print(f"  {sum(n for _, n in fonti.most_common()[15:]):5d}  (altre {len(fonti)-15} fonti)")

# --- lunghezza dell'enunciato -----------------------------------------------
lung = sorted(len(p.statement) for p in verificabili)
def perc(q):
    return lung[min(len(lung) - 1, int(q * len(lung)))]
print("\n" + "-" * 78)
print("LUNGHEZZA DELL'ENUNCIATO in caratteri (MISURATO)")
print("-" * 78)
print(f"  minimo {lung[0]}   25% {perc(.25)}   mediana {perc(.5)}   "
      f"75% {perc(.75)}   90% {perc(.9)}   massimo {lung[-1]}")
fasce = Counter()
for L in lung:
    fasce["fino a 100" if L <= 100 else
          "101-300" if L <= 300 else
          "301-1000" if L <= 1000 else "oltre 1000"] += 1
for f in ["fino a 100", "101-300", "301-1000", "oltre 1000"]:
    print(f"  {fasce.get(f,0):5d}  {f}")

# --- calcolabilita' ----------------------------------------------------------
# EURISTICA, non una misura. Un enunciato e' "forse esplorabile con un
# programma" se parla solo di oggetti finiti o numerabili con predicati
# decidibili, e NON menziona reali, limiti, insiemi infiniti, misure, topologia.
SEGNALI_NO = [
    "ℝ", "ℂ", "Real.", "Complex.", "Filter", "Tendsto", "liminf", "limsup",
    "Measure", "volume", "Topological", "Continuous", "Differentiable",
    "Infinite", "Set.Infinite", "Cardinal", "Ordinal", "deriv", "∫", "∑'",
    "Metric", "IsOpen", "IsClosed", "Compact", "Homeomorph", "Manifold",
]
SEGNALI_SI = ["ℕ", "ℤ", "Finset", "Fin ", "Nat.", "Int.", "Decidable", "SimpleGraph"]

def forse_esplorabile(p) -> bool:
    e = p.statement
    if any(s in e for s in SEGNALI_NO):
        return False
    return any(s in e for s in SEGNALI_SI)


espl = [p for p in verificabili if forse_esplorabile(p)]
print("\n" + "-" * 78)
print("FORSE ESPLORABILE CON UN PROGRAMMA (EURISTICA, non una misura)")
print("-" * 78)
print("  Regola: l'enunciato menziona oggetti discreti (ℕ, ℤ, Finset, Fin,")
print("  SimpleGraph, Decidable) e NON menziona reali, limiti, insiemi infiniti,")
print("  misure o topologia. E' un filtro grossolano: dice dove un calcolo")
print("  POTREBBE aiutare a cercare un esempio o un controesempio, non che il")
print("  problema sia decidibile.")
print(f"\n  {len(espl)} su {len(verificabili)} problemi aperti verificabili "
      f"({100*len(espl)/len(verificabili):.0f}%)")
sotto = Counter(forma_logica(p.statement) for p in espl)
print("\n  di questi, per forma logica:")
for f, n in sotto.most_common(8):
    print(f"    {n:5d}  {f}")
print("\n  I piu' promettenti per una ricerca automatica sono gli ESISTENZIALI:")
esist = [p for p in espl if "esistenziale" in forma_logica(p.statement)]
print(f"    {len(esist)} problemi. Un programma puo' cercare il testimone;")
print(f"    trovato il testimone, la dimostrazione Lean e' spesso breve.")
for p in esist[:10]:
    print(f"      {p.theorem}")
    print(f"        {p.statement[:110]}")
