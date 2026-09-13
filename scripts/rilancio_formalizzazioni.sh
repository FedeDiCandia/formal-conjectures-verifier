#!/usr/bin/env bash
# Rilancio del giro sulle prove note (13 settembre 2026): i 12 problemi di
# dati_ricerca/formalizzazioni_rilancio.json, cioe' i 7 non tentati o interrotti
# e i 5 falsati dalla rete, meno quelli gia' formalizzati altrove (passo 0).
#
# Il budget NON ha un valore predefinito: va deciso prima, sui numeri della Console.
# L'agente controlla da solo che caffeinate sia attivo e l'alimentatore collegato,
# e non parte altrimenti. Il coperchio va tenuto aperto.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$#" -ne 1 ]; then
  echo "uso: $0 BUDGET_IN_DOLLARI" >&2
  echo "     (nessun valore predefinito: il budget del rilancio va deciso prima)" >&2
  exit 2
fi
PROBLEMI=$(.venv/bin/python -c "import json;print(' '.join(v['problema'] for v in json.load(open('dati_ricerca/formalizzazioni_rilancio.json'))))")
exec env FCS_ARCHIVE="$PWD/external/fc-main" \
  FCS_LEAN4EXPORT="$PWD/external/lean4export-433/.lake/build/bin/lean4export" \
  FCS_INDEX="$PWD/verifier/problem_index_main.json" \
  .venv/bin/python -u agent/agente.py $PROBLEMI \
    --modello claude-opus-5 --effort low --istruzioni insistenti \
    --tetto-problema 1.00 --budget "$1" --max-iterazioni 40 \
    --rapporto runs/formalizzazioni-rilancio.json \
    --registro runs/lavori/formalizzazioni-rilancio.log
