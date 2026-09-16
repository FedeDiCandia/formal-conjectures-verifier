#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run.sh — command unico per i jobs lunghi del progetto.
#
#   ./run.sh estimate     <job> [opzioni]   quanto costerebbe, senza spendere
#   ./run.sh lancia    <job> [opzioni]   start_job (chiede conferma)
#   ./run.sh state                          cosa sta girando
#   ./run.sh segui     [name]               guarda il log che scorre
#   ./run.sh guarda [--segui]               che cosa sta facendo l'agente adesso
#   ./run.sh ferma     [name]               interrompe
#   ./run.sh resume  <name>               riparte dall'last_ checkpoint
#
# I jobs disponibili sono elencati da `./run.sh` senza arguments.
# ---------------------------------------------------------------------------
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOBS="$ROOT/runs/jobs"
PY="$ROOT/.venv/bin/python"
mkdir -p "$JOBS"

rosso()  { printf '\033[31m%s\033[0m\n' "$*"; }
verde()  { printf '\033[32m%s\033[0m\n' "$*"; }
giallo() { printf '\033[33m%s\033[0m\n' "$*"; }

uso() {
  cat <<'AIUTO'
run.sh — jobs lunghi del progetto

COMANDI
  estimate    <job> [opzioni]   dice quanto costerebbe e quanto durerebbe.
                                Non spende e non lancia niente.
  lancia   <job> [opzioni]   start_job il job in background. Chiede conferma
                                before di spendere, e tiene sveglio il computer.
  state                         listing dei jobs, con quelli attivi in cima.
  segui    [name]               mostra il log mentre scorre (Ctrl-C per uscire:
                                il job continua).
  ferma    [name]               interrompe un job. Senza name, li list_them.
  resume <name>               riparte dall'last_ checkpoint.

JOBS
  agente       Fa tentare a un agente one o piu' problems.
               opzioni:  --problems "A B C"   --budget N   --effort LIVELLO
               Esempio:  ./run.sh lancia agente --problems "Erdos366.erdos_366" --budget 2

  caccia       Esegue le ricerche di controesempi gia' preparate in
               runs/hunt/. Non usa l'API e non costa niente.
               opzioni:  --only_ NOME   --hours N

  snapshot     Prepara lo snapshot dell'archive da un commit fisso di main.
               Non usa l'API. Dura circa un'now_ e occupa one_ decina di GB.

  test         Esegue la suite di test del progetto.

ESEMPI
  ./run.sh estimate agente --problems "A B C" --budget 5
  ./run.sh lancia caccia --hours 8
  ./run.sh segui
  ./run.sh ferma caccia
AIUTO
}

# --------------------------------------------------------------------------
nome_lavoro() { echo "$1"; }
file_pid()    { echo "$JOBS/$1.pid"; }
log_file()    { echo "$JOBS/$1.log"; }
file_meta()   { echo "$JOBS/$1.meta"; }

attivo() {
  local pid_file; pid_file="$(file_pid "$1")"
  [ -f "$pid_file" ] || return 1
  local pid; pid="$(cat "$pid_file")"
  kill -0 "$pid" 2>/dev/null
}

# --------------------------------------------------------------------------
cmd_stima() {
  local job="${1:-}"; shift || true
  case "$job" in
    agente)
      "$PY" "$ROOT/scripts/estimate_cost.py" "$@"
      ;;
    caccia)
      echo "Lavoro: caccia ai controesempi"
      echo "  Costo in crediti API: ZERO. Gira only_ sul tuo computer."
      local n; n=$(ls "$ROOT/runs/hunt"/*.json 2>/dev/null | wc -l | tr -d ' ')
      echo "  Ricerche preparate: $n"
      echo "  Durata: quella che decidi con --hours (predefinito: finche' non la fermi)."
      echo "  Uso del computer: al maximum $(( $(sysctl -n hw.ncpu) - 2 )) core su $(sysctl -n hw.ncpu)."
      ;;
    snapshot)
      echo "Lavoro: preparazione dello snapshot da main"
      echo "  Costo in crediti API: ZERO."
      echo "  Durata: circa un'now_ (scaricamento della cache di Mathlib e compilazione)."
      echo "  Spazio su disco: circa 11 GB."
      echo "  Spazio libero adesso: $(df -g "$ROOT" | tail -1 | awk '{print $4}') GB."
      ;;
    test)
      echo "Lavoro: suite di test"
      echo "  Costo in crediti API: ZERO."
      echo "  Durata: circa 5 minuti."
      ;;
    *)
      rosso "Lavoro sconosciuto: '${job:-}'"; echo; uso; exit 2 ;;
  esac
}

# --------------------------------------------------------------------------
conferma() {
  local message="$1"
  echo
  giallo "$message"
  printf "Confermi? [scrivi si per procedere] "
  local answer; read -r answer
  case "$answer" in
    si|SI|Si|sì|SÌ|s|S|y|yes) return 0 ;;
    *) echo "Annullato."; return 1 ;;
  esac
}

cmd_lancia() {
  local job="${1:-}"; shift || true
  [ -n "$job" ] || { uso; exit 2; }

  if attivo "$job"; then
    rosso "Il job '$job' sta gia' girando (PID $(cat "$(file_pid "$job")"))."
    echo "Guardalo con:  ./run.sh segui $job"
    exit 1
  fi

  local command=()
  case "$job" in
    agente)
      cmd_stima agente "$@"
      conferma "Questo job SPENDE crediti API." || exit 0
      command=("$PY" "$ROOT/agent/agent.py" "$@")
      ;;
    caccia)
      cmd_stima caccia
      conferma "Questo job non spende crediti, ma tiene occupato il computer." || exit 0
      command=("$PY" "$ROOT/scripts/hunt.py" "$@")
      ;;
    snapshot)
      cmd_stima snapshot
      conferma "Scarichera' diversi GB e compilera' per circa un'now_." || exit 0
      command=(bash "$ROOT/scripts/setup_snapshot_main.sh")
      ;;
    test)
      command=("$PY" -m pytest "$ROOT/tests/" -v)
      ;;
    *) rosso "Lavoro sconosciuto: '$job'"; uso; exit 2 ;;
  esac

  local log; log="$(log_file "$job")"
  : > "$log"
  {
    echo "job: $job"
    echo "avviato: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "command: ${command[*]}"
  } > "$(file_meta "$job")"

  # `caffeinate -i` impedisce al computer di addormentarsi mentre work.
  # Senza, un job di otto hours si interrompe al prime_ coperchio chiuso.
  # Il distacco passa da scripts/distacca.py: `nohup ... &` da one_ shell che poi
  # exits non basta su macOS, il group di processi viene terminato comunque.
  "$PY" "$ROOT/scripts/distacca.py" "$job" -- caffeinate -i "${command[@]}"

  verde "Avviato '$job'."
  echo "  log:     $log"
  echo "  guarda:  ./run.sh segui $job"
  echo "  ferma:   ./run.sh ferma $job"
}

# --------------------------------------------------------------------------
# --- guarda: che cosa sta facendo l'agente, adesso -------------------------
# Serve quando un job e' state lanciato senza log da seguire: invece
# dell'output, guarda le TRACCE che l'agente lascia sul disco mentre work.
cmd_guarda() {
  # con --segui diventa un stream: la stessa fotografia ogni cinque seconds.
  # `watch` non c'e' su macOS, quindi si fa a mano.
  if [ "${1:-}" = "--segui" ]; then
    echo "Aggiorno ogni 5 seconds. Ctrl-C per smettere (il job continua)."
    sleep 1
    while true; do
      clear
      cmd_guarda
      echo "  ── aggiornamento fra 5 seconds, Ctrl-C per smettere ──"
      sleep 5
    done
  fi
  echo "════════════════════════════════════════════════════════════════"
  echo " CHE COSA STA FACENDO L'AGENTE"
  echo "════════════════════════════════════════════════════════════════"

  local lines
  lines=$(ps -eo etime,args | grep "[a]gent/agente.py" | head -1)
  if [ -z "$lines" ]; then
    echo
    echo "  Nessun agente in esecuzione."
  else
    echo
    echo "  In esecuzione da: $(echo "$lines" | awk '{print $1}')"
    echo "  Modello:          $(echo "$lines" | grep -o '\-\-model [^ ]*' | cut -d' ' -f2)"
    echo "  Budget:           $(echo "$lines" | grep -o '\-\-budget [^ ]*' | cut -d' ' -f2) dollari"
  fi

  echo
  echo "  ── I PROBLEMI, in order di lavorazione ──────────────────────"
  if [ -d "$ROOT/runs/job" ]; then
    # `tac` e' GNU e su macOS non esiste: `tail -r` fa la stessa cosa
    ls -t "$ROOT/runs/job" 2>/dev/null | tail -r | nl -w3 -s'. ' | sed 's/^/   /'
    echo
    echo "  L'last_ della list_ e' quello su cui sta lavorando adesso."
  else
    echo "   (nessuna folder di job ancora)"
  fi

  echo
  echo "  ── LEAN sta verificando in questo istante? ───────────────────"
  if pgrep -f "lean --" >/dev/null 2>&1 || pgrep -f "lake env" >/dev/null 2>&1; then
    echo "   sì: one_ check e' in corso (dura dai 30 seconds ai 2 minuti)"
  else
    echo "   no: in questo istante l'agente sta pensando o scrivendo code"
  fi

  echo
  echo "  ── L'ULTIMO PROGRAMMA che il model ha scritto da sé ────────"
  local last_
  last_=$(ls -t "$ROOT"/runs/job/*/program.py 2>/dev/null | head -1)
  if [ -n "$last_" ]; then
    echo "   da $(dirname "$last_" | xargs basename):"
    sed 's/^/     /' "$last_" | head -20
  else
    echo "   (nessuno: non ha ancora usato run_python)"
  fi

  echo
  echo "  ── SPESA ─────────────────────────────────────────────────────"
  local report
  report=$(ls -t "$ROOT"/runs/*.json 2>/dev/null | head -1)
  if [ -n "$report" ]; then
    "$PY" - "$report" <<'FINE'
import json, sys
from pathlib import Path
d = json.loads(Path(sys.argv[1]).read_text())
if "spent" in d:
    print(f"   last_ report: {Path(sys.argv[1]).name}")
    print(f"   spent ${d['spent']:.4f} su ${d['budget']:.2f}")
    ris = sum(1 for t in d.get('attempts', []) if t['solved_one'])
    print(f"   solved_ {ris} su {len(d.get('attempts', []))}")
FINE
  fi
  echo "   (mentre un giro e' in corso la spesa si vede only_ alla end:"
  echo "    il report viene scritto quando l'last_ problem e' finito)"
  echo
}

cmd_stato() {
  local found=0
  echo "JOBS ATTIVI"
  for pid_file in "$JOBS"/*.pid; do
    [ -e "$pid_file" ] || continue
    local n; n="$(basename "$pid_file" .pid)"
    if attivo "$n"; then
      found=1
      local pid; pid="$(cat "$pid_file")"
      local da; da="$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')"
      verde "  $n  (PID $pid, da $da)"
      tail -2 "$(log_file "$n")" 2>/dev/null | sed 's/^/      /'
    fi
  done
  [ "$found" = 1 ] || echo "  (nessuno)"

  echo
  echo "JOBS CONCLUSI"
  found=0
  for pid_file in "$JOBS"/*.pid; do
    [ -e "$pid_file" ] || continue
    local n; n="$(basename "$pid_file" .pid)"
    if ! attivo "$n"; then
      found=1
      local quando; quando="$(grep '^avviato' "$(file_meta "$n")" 2>/dev/null | cut -d' ' -f2-)"
      echo "  $n  (avviato $quando)"
      tail -1 "$(log_file "$n")" 2>/dev/null | sed 's/^/      /'
    fi
  done
  [ "$found" = 1 ] || echo "  (nessuno)"
}

# --------------------------------------------------------------------------
cmd_segui() {
  local n="${1:-}"
  if [ -z "$n" ]; then
    for pid_file in "$JOBS"/*.pid; do
      [ -e "$pid_file" ] || continue
      local c; c="$(basename "$pid_file" .pid)"
      if attivo "$c"; then n="$c"; break; fi
    done
  fi
  [ -n "$n" ] || { rosso "Nessun job attivo."; exit 1; }
  echo "Seguo '$n'. Ctrl-C per smettere di guardare (il job continua)."
  echo
  tail -f "$(log_file "$n")"
}

# --------------------------------------------------------------------------
cmd_ferma() {
  local n="${1:-}"
  if [ -z "$n" ]; then
    echo "Quale job? Quelli attivi sono:"
    cmd_stato
    exit 2
  fi
  attivo "$n" || { giallo "Il job '$n' non sta girando."; exit 0; }
  local pid; pid="$(cat "$(file_pid "$n")")"
  # SIGTERM al group: i jobs salvano il checkpoint e chiudono
  kill -TERM "-$(ps -o pgid= -p "$pid" | tr -d ' ')" 2>/dev/null || kill -TERM "$pid"
  sleep 3
  if attivo "$n"; then
    giallo "Non si e' fermato con garbo, lo termino."
    kill -KILL "-$(ps -o pgid= -p "$pid" | tr -d ' ')" 2>/dev/null || kill -KILL "$pid"
  fi
  verde "Fermato '$n'. Riprendi con:  ./run.sh resume $n"
}

# --------------------------------------------------------------------------
cmd_riprendi() {
  local n="${1:-}"; shift || true
  [ -n "$n" ] || { rosso "Quale job riprendo?"; exit 2; }
  case "$n" in
    caccia)
      "$0" lancia caccia --resume "$@"
      ;;
    snapshot)
      # lo script e' idempotente: ripartire e' sicuro
      "$0" lancia snapshot
      ;;
    *)
      rosso "Il job '$n' non ha un checkpoint da cui ripartire."
      echo "Rilancialo da capo con:  ./run.sh lancia $n"
      exit 1 ;;
  esac
}

# --------------------------------------------------------------------------
case "${1:-}" in
  estimate)    shift; cmd_stima "$@" ;;
  lancia)   shift; cmd_lancia "$@" ;;
  state)    shift; cmd_stato ;;
  guarda)   shift; cmd_guarda "$@" ;;
  segui)    shift; cmd_segui "$@" ;;
  ferma)    shift; cmd_ferma "$@" ;;
  resume) shift; cmd_riprendi "$@" ;;
  ""|-h|--help|aiuto) uso ;;
  *) rosso "Comando sconosciuto: $1"; echo; uso; exit 2 ;;
esac
