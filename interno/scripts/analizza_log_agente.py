"""
Estrae i numeri MISURATI dal log di un'esecuzione dell'agente.

Legge il log invece di ricopiare i numeri a mano: cosi' sono verificabili e
non c'e' modo di sbagliarli o inventarli. Quello che il log non contiene viene
dichiarato NON MISURATO, non stimato.
"""
import re
import sys
from pathlib import Path

log = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")

print("=" * 78)
print(f"ANALISI DEL LOG: {sys.argv[1]}")
print("=" * 78)

# --- intestazione
for chiave, schema in [("modello/effort", r"Modello: (\S+) \| effort: (\S+)"),
                       ("budget", r"Budget totale: \$([\d.]+)\s+\(tetto per problema: \$([\d.]+)\)"),
                       ("problemi in coda", r"Problemi: (\d+)")]:
    m = re.search(schema, log)
    print(f"  {chiave:18} {' '.join(m.groups()) if m else 'non presente nel log'}")

# --- problemi affrontati
problemi = re.findall(r"^\[(\d+)/(\d+)\] (\S+)\s+\((.+?)\)$", log, re.M)
print(f"\n  problemi effettivamente iniziati: {len(problemi)}")
for i, tot, nome, cat in problemi:
    print(f"    {i}/{tot}  {nome}  [{cat}]")

# --- iterazioni: la spesa mostrata e' quella PRIMA di quell'iterazione
spese = [(int(n), float(s)) for n, s in
         re.findall(r"iterazione (\d+)\s+\[spesa \$([\d.]+)", log)]
print(f"\n  iterazioni avviate (MISURATO): {len(spese)}")

# --- riga di chiusura per problema
chiusure = re.findall(
    r"=> (RISOLTO|non risolto): (.+?)\n\s+(\d+) iterazioni, (\d+) verifiche Lean, "
    r"(\d+) esecuzioni Python, (\d+)s, \$([\d.]+)", log)

print("\n" + "-" * 78)
print("PER PROBLEMA (tutti MISURATI: presi dalla riga di chiusura del log)")
print("-" * 78)
for esito, motivo, iters, ver, py, sec, costo in chiusure:
    print(f"  esito           {esito}")
    print(f"  motivo          {motivo}")
    print(f"  iterazioni      {iters}")
    print(f"  verifiche Lean  {ver}")
    print(f"  esecuzioni py   {py}")
    print(f"  tempo           {sec} s  ({int(sec)/60:.1f} min)")
    print(f"  costo           ${costo}")
    if int(ver) > 0:
        print(f"  costo medio per verifica Lean  ${float(costo)/int(ver):.4f}")
    if int(iters) > 0:
        print(f"  tempo medio per iterazione     {int(sec)/int(iters):.0f} s")

# --- costo per singola iterazione, per differenza.
# Va segmentato per problema: l'iterazione 1 del problema successivo riparte da
# 1 e la sua spesa progressiva coincide con il totale del problema precedente.
segmenti, corrente = [], []
for n, s in spese:
    if n == 1 and corrente:
        segmenti.append(corrente); corrente = []
    corrente.append((n, s))
if corrente:
    segmenti.append(corrente)
spese = segmenti[0] if segmenti else []
if len(segmenti) > 1:
    print(f"\n  NB: il log contiene {len(segmenti)} problemi iniziati; l'analisi delle")
    print(f"      chiamate riguarda il primo, l'unico completato prima dell'interruzione.")

if len(spese) >= 2:
    print("\n" + "-" * 78)
    print("COSTO DI CIASCUNA CHIAMATA (MISURATO, per differenza dei totali)")
    print("-" * 78)
    costi = []
    for (n1, s1), (n2, s2) in zip(spese, spese[1:]):
        costi.append((n1, s2 - s1))
    # l'ultima iterazione: differenza fra il totale finale e l'ultimo progressivo
    if chiusure:
        finale = float(chiusure[0][6])
        costi.append((spese[-1][0], finale - spese[-1][1]))
    for n, c in costi:
        barra = "#" * max(1, int(c * 100))
        print(f"    iterazione {n:2d}  ${c:.4f}  {barra}")
    valori = [c for _, c in costi]
    print(f"\n    chiamate: {len(valori)}")
    print(f"    minimo:   ${min(valori):.4f}")
    print(f"    massimo:  ${max(valori):.4f}")
    print(f"    media:    ${sum(valori)/len(valori):.4f}")
    ordinati = sorted(valori)
    mediana = (ordinati[len(ordinati)//2] if len(ordinati) % 2
               else (ordinati[len(ordinati)//2 - 1] + ordinati[len(ordinati)//2]) / 2)
    print(f"    mediana:  ${mediana:.4f}")

# --- sforamento del tetto
m = re.search(r"tetto di spesa per questo problema \(\$([\d.]+) su \$([\d.]+)\)", log)
if m:
    speso, tetto = float(m.group(1)), float(m.group(2))
    print("\n" + "-" * 78)
    print("SFORAMENTO DEL TETTO (MISURATO)")
    print("-" * 78)
    print(f"    tetto ${tetto:.2f}  ->  speso ${speso:.4f}   "
          f"sforamento ${speso-tetto:.4f} ({100*(speso-tetto)/tetto:.0f}%)")
    print("    Causa: il controllo era solo A POSTERIORI. Corretto poi con la")
    print("    stima del costo massimo PRIMA di ogni chiamata (agent/costi.py).")

# --- token
if "chiamate | input" in log:
    for m in re.finditer(r"(\d+) chiamate \| input ([\d,]+) \| cache scritta ([\d,]+)"
                         r"(?: \(\+[\d,]+ a 1h\))? \| cache letta ([\d,]+) \| "
                         r"output ([\d,]+) \| costo \$([\d.]+)", log):
        print("\n" + "-" * 78)
        print("TOKEN (MISURATO)")
        print("-" * 78)
        print(f"    chiamate {m.group(1)} | input {m.group(2)} | cache scritta {m.group(3)} "
              f"| cache letta {m.group(4)} | output {m.group(5)} | ${m.group(6)}")
else:
    print("\n" + "-" * 78)
    print("TOKEN: NON MISURATO")
    print("-" * 78)
    print("    Il riepilogo dei token viene stampato solo alla fine dell'esecuzione,")
    print("    e questa e' stata interrotta prima. Il costo totale e' noto, ma la sua")
    print("    scomposizione in input / output / cache NON e' ricostruibile: una sola")
    print("    equazione con quattro incognite. Non la stimo.")

# --- ragionamenti: segnali su cosa ha fatto fallire
print("\n" + "-" * 78)
print("SEGNALI DAI RAGIONAMENTI (MISURATO: citazioni testuali dal log)")
print("-" * 78)
temi = {
    "messaggi info di Lean mancanti":
        r"info messages (aren't|don't) (showing|display)",
    "aggiramento tramite errori provocati":
        r"trick the system into erroring|forcing a type mismatch|provoc",
    "messaggio troncato alla prima riga":
        r"error message gets truncated",
    "considerato l'uso di sorry per esplorare":
        r"adding a theorem with sorry",
    "considerato run_cmd / run_tac (bloccati dal guard)":
        r"run_cmd|run_tac",
    "esplorazione dell'API di Mathlib":
        r"pin down the exact Mathlib API|search the environment for existing helper",
}
for etichetta, schema in temi.items():
    n = len(re.findall(schema, log, re.I))
    if n:
        print(f"    {n:2d}x  {etichetta}")
