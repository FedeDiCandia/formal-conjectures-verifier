#!/usr/bin/env bash
# Rilancio del giro sulle prove note.
#
# uso: scripts/rilancio_formalizzazioni.sh BUDGET [LISTA.json]
#   BUDGET  obbligatorio, in dollari: nessun valore predefinito, va deciso prima
#   LISTA   elenco dei problemi (predefinito: dati_ricerca/formalizzazioni_rilancio.json);
#           rapporto e registro prendono il nome della lista
#
# L'agente controlla da solo che caffeinate sia attivo e l'alimentatore collegato,
# e non parte altrimenti. Il coperchio va tenuto aperto.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "uso: $0 BUDGET_IN_DOLLARI [LISTA.json]" >&2
  echo "     (nessun valore predefinito per il budget: va deciso prima)" >&2
  exit 2
fi
LISTA="${2:-dati_ricerca/formalizzazioni_rilancio.json}"
NOME=$(basename "$LISTA" .json)
PROBLEMI=$(.venv/bin/python -c "import json,sys;print(' '.join(v['problema'] for v in json.load(open(sys.argv[1]))))" "$LISTA")
exec env FCS_ARCHIVE="$PWD/external/fc-main" \
  FCS_LEAN4EXPORT="$PWD/external/lean4export-433/.lake/build/bin/lean4export" \
  FCS_INDEX="$PWD/verifier/problem_index_main.json" \
  .venv/bin/python -u agent/agente.py $PROBLEMI \
    --modello claude-opus-5 --effort low --istruzioni insistenti \
    --tetto-problema 1.00 --budget "$1" --max-iterazioni 40 \
    --rapporto "runs/$NOME.json" \
    --registro "runs/lavori/$NOME.log"
