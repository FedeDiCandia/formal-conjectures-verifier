#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# avvia.sh — comando unico per i lavori lunghi del progetto.
#
#   ./avvia.sh stima     <lavoro> [opzioni]   quanto costerebbe, senza spendere
#   ./avvia.sh lancia    <lavoro> [opzioni]   avvia (chiede conferma)
#   ./avvia.sh stato                          cosa sta girando
#   ./avvia.sh segui     [nome]               guarda il log che scorre
#   ./avvia.sh guarda [--segui]               che cosa sta facendo l'agente adesso
#   ./avvia.sh ferma     [nome]               interrompe
#   ./avvia.sh riprendi  <nome>               riparte dall'ultimo checkpoint
#
# I lavori disponibili sono elencati da `./avvia.sh` senza argomenti.
# ---------------------------------------------------------------------------
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAVORI="$ROOT/runs/lavori"
PY="$ROOT/.venv/bin/python"
mkdir -p "$LAVORI"

rosso()  { printf '\033[31m%s\033[0m\n' "$*"; }
verde()  { printf '\033[32m%s\033[0m\n' "$*"; }
giallo() { printf '\033[33m%s\033[0m\n' "$*"; }

uso() {
  cat <<'AIUTO'
avvia.sh — lavori lunghi del progetto

COMANDI
  stima    <lavoro> [opzioni]   dice quanto costerebbe e quanto durerebbe.
                                Non spende e non lancia niente.
  lancia   <lavoro> [opzioni]   avvia il lavoro in background. Chiede conferma
                                prima di spendere, e tiene sveglio il computer.
  stato                         elenco dei lavori, con quelli attivi in cima.
  segui    [nome]               mostra il log mentre scorre (Ctrl-C per uscire:
                                il lavoro continua).
  ferma    [nome]               interrompe un lavoro. Senza nome, li elenca.
  riprendi <nome>               riparte dall'ultimo checkpoint.

LAVORI
  agente       Fa tentare a un agente uno o piu' problemi.
               opzioni:  --problemi "A B C"   --budget N   --effort LIVELLO
               Esempio:  ./avvia.sh lancia agente --problemi "Erdos366.erdos_366" --budget 2

  caccia       Esegue le ricerche di controesempi gia' preparate in
               runs/caccia/. Non usa l'API e non costa niente.
               opzioni:  --solo NOME   --ore N

  snapshot     Prepara lo snapshot dell'archivio da un commit fisso di main.
               Non usa l'API. Dura circa un'ora e occupa una decina di GB.

  test         Esegue la suite di test del progetto.

ESEMPI
  ./avvia.sh stima agente --problemi "A B C" --budget 5
  ./avvia.sh lancia caccia --ore 8
  ./avvia.sh segui
  ./avvia.sh ferma caccia
AIUTO
}

# --------------------------------------------------------------------------
nome_lavoro() { echo "$1"; }
file_pid()    { echo "$LAVORI/$1.pid"; }
file_log()    { echo "$LAVORI/$1.log"; }
file_meta()   { echo "$LAVORI/$1.meta"; }

attivo() {
  local pid_file; pid_file="$(file_pid "$1")"
  [ -f "$pid_file" ] || return 1
  local pid; pid="$(cat "$pid_file")"
  kill -0 "$pid" 2>/dev/null
}

# --------------------------------------------------------------------------
cmd_stima() {
  local lavoro="${1:-}"; shift || true
  case "$lavoro" in
    agente)
      "$PY" "$ROOT/scripts/stima_costo.py" "$@"
      ;;
    caccia)
      echo "Lavoro: caccia ai controesempi"
      echo "  Costo in crediti API: ZERO. Gira solo sul tuo computer."
      local n; n=$(ls "$ROOT/runs/caccia"/*.json 2>/dev/null | wc -l | tr -d ' ')
      echo "  Ricerche preparate: $n"
      echo "  Durata: quella che decidi con --ore (predefinito: finche' non la fermi)."
      echo "  Uso del computer: al massimo $(( $(sysctl -n hw.ncpu) - 2 )) core su $(sysctl -n hw.ncpu)."
      ;;
    snapshot)
      echo "Lavoro: preparazione dello snapshot da main"
      echo "  Costo in crediti API: ZERO."
      echo "  Durata: circa un'ora (scaricamento della cache di Mathlib e compilazione)."
      echo "  Spazio su disco: circa 11 GB."
      echo "  Spazio libero adesso: $(df -g "$ROOT" | tail -1 | awk '{print $4}') GB."
      ;;
    test)
      echo "Lavoro: suite di test"
      echo "  Costo in crediti API: ZERO."
      echo "  Durata: circa 5 minuti."
      ;;
    *)
      rosso "Lavoro sconosciuto: '${lavoro:-}'"; echo; uso; exit 2 ;;
  esac
}

# --------------------------------------------------------------------------
conferma() {
  local messaggio="$1"
  echo
  giallo "$messaggio"
  printf "Confermi? [scrivi si per procedere] "
  local risposta; read -r risposta
  case "$risposta" in
    si|SI|Si|sì|SÌ|s|S|y|yes) return 0 ;;
    *) echo "Annullato."; return 1 ;;
  esac
}

cmd_lancia() {
  local lavoro="${1:-}"; shift || true
  [ -n "$lavoro" ] || { uso; exit 2; }

  if attivo "$lavoro"; then
    rosso "Il lavoro '$lavoro' sta gia' girando (PID $(cat "$(file_pid "$lavoro")"))."
    echo "Guardalo con:  ./avvia.sh segui $lavoro"
    exit 1
  fi

  local comando=()
  case "$lavoro" in
    agente)
      cmd_stima agente "$@"
      conferma "Questo lavoro SPENDE crediti API." || exit 0
      comando=("$PY" "$ROOT/agent/agente.py" "$@")
      ;;
    caccia)
      cmd_stima caccia
      conferma "Questo lavoro non spende crediti, ma tiene occupato il computer." || exit 0
      comando=("$PY" "$ROOT/scripts/caccia.py" "$@")
      ;;
    snapshot)
      cmd_stima snapshot
      conferma "Scarichera' diversi GB e compilera' per circa un'ora." || exit 0
      comando=(bash "$ROOT/scripts/setup_snapshot_main.sh")
      ;;
    test)
      comando=("$PY" -m pytest "$ROOT/tests/" -v)
      ;;
    *) rosso "Lavoro sconosciuto: '$lavoro'"; uso; exit 2 ;;
  esac

  local log; log="$(file_log "$lavoro")"
  : > "$log"
  {
    echo "lavoro: $lavoro"
    echo "avviato: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "comando: ${comando[*]}"
  } > "$(file_meta "$lavoro")"

  # `caffeinate -i` impedisce al computer di addormentarsi mentre lavora.
  # Senza, un lavoro di otto ore si interrompe al primo coperchio chiuso.
  # Il distacco passa da scripts/distacca.py: `nohup ... &` da una shell che poi
  # esce non basta su macOS, il gruppo di processi viene terminato comunque.
  "$PY" "$ROOT/scripts/distacca.py" "$lavoro" -- caffeinate -i "${comando[@]}"

  verde "Avviato '$lavoro'."
  echo "  log:     $log"
  echo "  guarda:  ./avvia.sh segui $lavoro"
  echo "  ferma:   ./avvia.sh ferma $lavoro"
}

# --------------------------------------------------------------------------
# --- guarda: che cosa sta facendo l'agente, adesso -------------------------
# Serve quando un lavoro e' stato lanciato senza log da seguire: invece
# dell'output, guarda le TRACCE che l'agente lascia sul disco mentre lavora.
cmd_guarda() {
  # con --segui diventa un flusso: la stessa fotografia ogni cinque secondi.
  # `watch` non c'e' su macOS, quindi si fa a mano.
  if [ "${1:-}" = "--segui" ]; then
    echo "Aggiorno ogni 5 secondi. Ctrl-C per smettere (il lavoro continua)."
    sleep 1
    while true; do
      clear
      cmd_guarda
      echo "  ── aggiornamento fra 5 secondi, Ctrl-C per smettere ──"
      sleep 5
    done
  fi
  echo "════════════════════════════════════════════════════════════════"
  echo " CHE COSA STA FACENDO L'AGENTE"
  echo "════════════════════════════════════════════════════════════════"

  local righe
  righe=$(ps -eo etime,args | grep "[a]gent/agente.py" | head -1)
  if [ -z "$righe" ]; then
    echo
    echo "  Nessun agente in esecuzione."
  else
    echo
    echo "  In esecuzione da: $(echo "$righe" | awk '{print $1}')"
    echo "  Modello:          $(echo "$righe" | grep -o '\-\-modello [^ ]*' | cut -d' ' -f2)"
    echo "  Budget:           $(echo "$righe" | grep -o '\-\-budget [^ ]*' | cut -d' ' -f2) dollari"
  fi

  echo
  echo "  ── I PROBLEMI, in ordine di lavorazione ──────────────────────"
  if [ -d "$ROOT/runs/lavoro" ]; then
    # `tac` e' GNU e su macOS non esiste: `tail -r` fa la stessa cosa
    ls -t "$ROOT/runs/lavoro" 2>/dev/null | tail -r | nl -w3 -s'. ' | sed 's/^/   /'
    echo
    echo "  L'ultimo della lista e' quello su cui sta lavorando adesso."
  else
    echo "   (nessuna cartella di lavoro ancora)"
  fi

  echo
  echo "  ── LEAN sta verificando in questo istante? ───────────────────"
  if pgrep -f "lean --" >/dev/null 2>&1 || pgrep -f "lake env" >/dev/null 2>&1; then
    echo "   sì: una verifica e' in corso (dura dai 30 secondi ai 2 minuti)"
  else
    echo "   no: in questo istante l'agente sta pensando o scrivendo codice"
  fi

  echo
  echo "  ── L'ULTIMO PROGRAMMA che il modello ha scritto da sé ────────"
  local ultimo
  ultimo=$(ls -t "$ROOT"/runs/lavoro/*/programma.py 2>/dev/null | head -1)
  if [ -n "$ultimo" ]; then
    echo "   da $(dirname "$ultimo" | xargs basename):"
    sed 's/^/     /' "$ultimo" | head -20
  else
    echo "   (nessuno: non ha ancora usato run_python)"
  fi

  echo
  echo "  ── SPESA ─────────────────────────────────────────────────────"
  local rapporto
  rapporto=$(ls -t "$ROOT"/runs/*.json 2>/dev/null | head -1)
  if [ -n "$rapporto" ]; then
    "$PY" - "$rapporto" <<'FINE'
import json, sys
from pathlib import Path
d = json.loads(Path(sys.argv[1]).read_text())
if "speso" in d:
    print(f"   ultimo rapporto: {Path(sys.argv[1]).name}")
    print(f"   speso ${d['speso']:.4f} su ${d['budget']:.2f}")
    ris = sum(1 for t in d.get('tentativi', []) if t['risolto'])
    print(f"   risolti {ris} su {len(d.get('tentativi', []))}")
FINE
  fi
  echo "   (mentre un giro e' in corso la spesa si vede solo alla fine:"
  echo "    il rapporto viene scritto quando l'ultimo problema e' finito)"
  echo
}

cmd_stato() {
  local trovati=0
  echo "LAVORI ATTIVI"
  for pid_file in "$LAVORI"/*.pid; do
    [ -e "$pid_file" ] || continue
    local n; n="$(basename "$pid_file" .pid)"
    if attivo "$n"; then
      trovati=1
      local pid; pid="$(cat "$pid_file")"
      local da; da="$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')"
      verde "  $n  (PID $pid, da $da)"
      tail -2 "$(file_log "$n")" 2>/dev/null | sed 's/^/      /'
    fi
  done
  [ "$trovati" = 1 ] || echo "  (nessuno)"

  echo
  echo "LAVORI CONCLUSI"
  trovati=0
  for pid_file in "$LAVORI"/*.pid; do
    [ -e "$pid_file" ] || continue
    local n; n="$(basename "$pid_file" .pid)"
    if ! attivo "$n"; then
      trovati=1
      local quando; quando="$(grep '^avviato' "$(file_meta "$n")" 2>/dev/null | cut -d' ' -f2-)"
      echo "  $n  (avviato $quando)"
      tail -1 "$(file_log "$n")" 2>/dev/null | sed 's/^/      /'
    fi
  done
  [ "$trovati" = 1 ] || echo "  (nessuno)"
}

# --------------------------------------------------------------------------
cmd_segui() {
  local n="${1:-}"
  if [ -z "$n" ]; then
    for pid_file in "$LAVORI"/*.pid; do
      [ -e "$pid_file" ] || continue
      local c; c="$(basename "$pid_file" .pid)"
      if attivo "$c"; then n="$c"; break; fi
    done
  fi
  [ -n "$n" ] || { rosso "Nessun lavoro attivo."; exit 1; }
  echo "Seguo '$n'. Ctrl-C per smettere di guardare (il lavoro continua)."
  echo
  tail -f "$(file_log "$n")"
}

# --------------------------------------------------------------------------
cmd_ferma() {
  local n="${1:-}"
  if [ -z "$n" ]; then
    echo "Quale lavoro? Quelli attivi sono:"
    cmd_stato
    exit 2
  fi
  attivo "$n" || { giallo "Il lavoro '$n' non sta girando."; exit 0; }
  local pid; pid="$(cat "$(file_pid "$n")")"
  # SIGTERM al gruppo: i lavori salvano il checkpoint e chiudono
  kill -TERM "-$(ps -o pgid= -p "$pid" | tr -d ' ')" 2>/dev/null || kill -TERM "$pid"
  sleep 3
  if attivo "$n"; then
    giallo "Non si e' fermato con garbo, lo termino."
    kill -KILL "-$(ps -o pgid= -p "$pid" | tr -d ' ')" 2>/dev/null || kill -KILL "$pid"
  fi
  verde "Fermato '$n'. Riprendi con:  ./avvia.sh riprendi $n"
}

# --------------------------------------------------------------------------
cmd_riprendi() {
  local n="${1:-}"; shift || true
  [ -n "$n" ] || { rosso "Quale lavoro riprendo?"; exit 2; }
  case "$n" in
    caccia)
      "$0" lancia caccia --riprendi "$@"
      ;;
    snapshot)
      # lo script e' idempotente: ripartire e' sicuro
      "$0" lancia snapshot
      ;;
    *)
      rosso "Il lavoro '$n' non ha un checkpoint da cui ripartire."
      echo "Rilancialo da capo con:  ./avvia.sh lancia $n"
      exit 1 ;;
  esac
}

# --------------------------------------------------------------------------
case "${1:-}" in
  stima)    shift; cmd_stima "$@" ;;
  lancia)   shift; cmd_lancia "$@" ;;
  stato)    shift; cmd_stato ;;
  guarda)   shift; cmd_guarda "$@" ;;
  segui)    shift; cmd_segui "$@" ;;
  ferma)    shift; cmd_ferma "$@" ;;
  riprendi) shift; cmd_riprendi "$@" ;;
  ""|-h|--help|aiuto) uso ;;
  *) rosso "Comando sconosciuto: $1"; echo; uso; exit 2 ;;
esac
