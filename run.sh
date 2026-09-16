#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run.sh — the single command for the project's long jobs.
#
#   ./run.sh estimate <job> [options]   what it would cost, without spending
#   ./run.sh launch   <job> [options]   start it (asks for confirmation)
#   ./run.sh status                     what is running
#   ./run.sh follow   [name]            watch the log as it scrolls
#   ./run.sh watch    [--follow]        what the agent is doing right now
#   ./run.sh stop     [name]            interrupt it
#   ./run.sh resume   <name>            restart from the last checkpoint
#
# The available jobs are listed by `./run.sh` with no arguments.
# ---------------------------------------------------------------------------
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOBS="$ROOT/runs/jobs"
PY="$ROOT/.venv/bin/python"
mkdir -p "$JOBS"

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }

usage() {
  cat <<'HELP'
run.sh — the project's long jobs

COMMANDS
  estimate <job> [options]   says what it would cost and how long it would take.
                             It spends nothing and launches nothing.
  launch   <job> [options]   starts the job in the background. It asks before
                             spending, and keeps the machine awake.
  status                     lists the jobs, active ones first.
  follow   [name]            shows the log as it scrolls (Ctrl-C to leave:
                             the job carries on).
  watch    [--follow]        what the agent is doing right now.
  stop     [name]            interrupts a job. With no name, lists them.
  resume   <name>            restarts from the last checkpoint.

JOBS
  agent        Has an agent attempt one or more problems.
               options:  --problems "A B C"   --budget N   --effort LEVEL
               Example:  ./run.sh launch agent --problems "Erdos366.erdos_366" --budget 2

  hunt         Runs the counterexample searches already prepared in
               runs/hunt/. It does not use the API and costs nothing.
               options:  --only NAME   --hours N

  snapshot     Prepares the archive snapshot from a fixed commit of main.
               It does not use the API. It takes about an hour and some tens of GB.

  test         Runs the project's test suite.

EXAMPLES
  ./run.sh estimate agent --problems "A B C" --budget 5
  ./run.sh launch hunt --hours 8
  ./run.sh follow
  ./run.sh stop hunt
HELP
}

# --------------------------------------------------------------------------
pid_file()  { echo "$JOBS/$1.pid"; }
log_file()  { echo "$JOBS/$1.log"; }
meta_file() { echo "$JOBS/$1.meta"; }

active() {
  local f; f="$(pid_file "$1")"
  [ -f "$f" ] || return 1
  local pid; pid="$(cat "$f")"
  kill -0 "$pid" 2>/dev/null
}

# --------------------------------------------------------------------------
cmd_estimate() {
  local job="${1:-}"; shift || true
  case "$job" in
    agent)
      "$PY" "$ROOT/scripts/estimate_cost.py" "$@"
      ;;
    hunt)
      echo "Job: the counterexample hunt"
      echo "  Cost in API credit: ZERO. It runs entirely on your machine."
      local n; n=$(ls "$ROOT/runs/hunt"/*.json 2>/dev/null | wc -l | tr -d ' ')
      echo "  Searches prepared: $n"
      echo "  Duration: whatever you set with --hours (default: until you stop it)."
      echo "  Machine use: at most $(( $(sysctl -n hw.ncpu) - 2 )) cores of $(sysctl -n hw.ncpu)."
      ;;
    snapshot)
      echo "Job: preparing the snapshot from main"
      echo "  Cost in API credit: ZERO."
      echo "  Duration: about an hour (downloading Mathlib's cache and building)."
      echo "  Disk space: about 11 GB."
      echo "  Free space now: $(df -g "$ROOT" | tail -1 | awk '{print $4}') GB."
      ;;
    test)
      echo "Job: the test suite"
      echo "  Cost in API credit: ZERO."
      echo "  Duration: about 6 minutes."
      ;;
    *)
      red "Unknown job: '${job:-}'"; echo; usage; exit 2 ;;
  esac
}

# --------------------------------------------------------------------------
confirm() {
  local message="$1"
  echo
  yellow "$message"
  printf "Confirm? [type yes to proceed] "
  local answer; read -r answer
  case "$answer" in
    y|Y|yes|YES|Yes) return 0 ;;
    *) echo "Cancelled."; return 1 ;;
  esac
}

cmd_launch() {
  local job="${1:-}"; shift || true
  [ -n "$job" ] || { usage; exit 2; }

  if active "$job"; then
    red "The job '$job' is already running (PID $(cat "$(pid_file "$job")"))."
    echo "Watch it with:  ./run.sh follow $job"
    exit 1
  fi

  local command=()
  case "$job" in
    agent)
      cmd_estimate agent "$@"
      confirm "This job SPENDS API credit." || exit 0
      command=("$PY" "$ROOT/agent/agent.py" "$@")
      ;;
    hunt)
      cmd_estimate hunt
      confirm "This job spends no credit, but it keeps the machine busy." || exit 0
      command=("$PY" "$ROOT/scripts/hunt.py" "$@")
      ;;
    snapshot)
      cmd_estimate snapshot
      confirm "It will download several GB and build for about an hour." || exit 0
      command=(bash "$ROOT/scripts/setup_snapshot_main.sh")
      ;;
    test)
      command=("$PY" -m pytest "$ROOT/tests/" -v)
      ;;
    *) red "Unknown job: '$job'"; usage; exit 2 ;;
  esac

  local log; log="$(log_file "$job")"
  : > "$log"
  {
    echo "job: $job"
    echo "started: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "command: ${command[*]}"
  } > "$(meta_file "$job")"

  # `caffeinate -i` stops the machine falling asleep while it works. Without it an
  # eight-hour job dies the first time the lid is closed. Detaching goes through
  # scripts/detach.py: `nohup ... &` from a shell that then exits is not enough on
  # macOS, the process group is killed anyway.
  "$PY" "$ROOT/scripts/detach.py" "$job" -- caffeinate -i "${command[@]}"

  green "Started '$job'."
  echo "  log:    $log"
  echo "  watch:  ./run.sh follow $job"
  echo "  stop:   ./run.sh stop $job"
}

# --------------------------------------------------------------------------
# --- watch: what the agent is doing, right now ----------------------------
# This is for when a job was launched with no log to follow: instead of the
# output, it looks at the TRACES the agent leaves on disk while it works.
cmd_watch() {
  # with --follow it becomes a stream: the same snapshot every five seconds.
  # `watch` does not exist on macOS, so it is done by hand.
  if [ "${1:-}" = "--follow" ]; then
    echo "Refreshing every 5 seconds. Ctrl-C to stop (the job carries on)."
    sleep 1
    while true; do
      clear
      cmd_watch
      echo "  ── refresh in 5 seconds, Ctrl-C to stop ──"
      sleep 5
    done
  fi
  echo "════════════════════════════════════════════════════════════════"
  echo " WHAT THE AGENT IS DOING"
  echo "════════════════════════════════════════════════════════════════"

  local lines
  lines=$(ps -eo etime,args | grep "[a]gent/agent.py" | head -1)
  if [ -z "$lines" ]; then
    echo
    echo "  No agent running."
  else
    echo
    echo "  Running for:  $(echo "$lines" | awk '{print $1}')"
    echo "  Model:        $(echo "$lines" | grep -o '\-\-model [^ ]*' | cut -d' ' -f2)"
    echo "  Budget:       $(echo "$lines" | grep -o '\-\-budget [^ ]*' | cut -d' ' -f2) dollars"
  fi

  echo
  echo "  ── THE PROBLEMS, in the order they are worked on ─────────────"
  if [ -d "$ROOT/runs/job" ]; then
    # `tac` is GNU and does not exist on macOS: `tail -r` does the same
    ls -t "$ROOT/runs/job" 2>/dev/null | tail -r | nl -w3 -s'. ' | sed 's/^/   /'
    echo
    echo "  The last in the list is the one it is working on now."
  else
    echo "   (no working directory yet)"
  fi

  echo
  echo "  ── is LEAN verifying at this instant? ────────────────────────"
  if pgrep -f "lean --" >/dev/null 2>&1 || pgrep -f "lake env" >/dev/null 2>&1; then
    echo "   yes: a verification is in progress (30 seconds to 2 minutes)"
  else
    echo "   no: right now the agent is thinking or writing code"
  fi

  echo
  echo "  ── THE LAST PROGRAM the model wrote by itself ────────────────"
  local last
  last=$(ls -t "$ROOT"/runs/job/*/program.py 2>/dev/null | head -1)
  if [ -n "$last" ]; then
    echo "   from $(dirname "$last" | xargs basename):"
    sed 's/^/     /' "$last" | head -20
  else
    echo "   (none: it has not used run_python yet)"
  fi

  echo
  echo "  ── SPEND ─────────────────────────────────────────────────────"
  local report
  report=$(ls -t "$ROOT"/runs/*.json 2>/dev/null | head -1)
  if [ -n "$report" ]; then
    "$PY" - "$report" <<'END'
import json, sys
from pathlib import Path
d = json.loads(Path(sys.argv[1]).read_text())
if "spent" in d:
    print(f"   last report: {Path(sys.argv[1]).name}")
    print(f"   spent ${d['spent']:.4f} of ${d['budget']:.2f}")
    solved = sum(1 for t in d.get('attempts', []) if t['solved'])
    print(f"   solved {solved} of {len(d.get('attempts', []))}")
END
  fi
  echo "   (while a run is in progress the spend only shows at the end:"
  echo "    the report is written when the last problem has finished)"
  echo
}

cmd_status() {
  local found=0
  echo "ACTIVE JOBS"
  for f in "$JOBS"/*.pid; do
    [ -e "$f" ] || continue
    local n; n="$(basename "$f" .pid)"
    if active "$n"; then
      found=1
      local pid; pid="$(cat "$f")"
      local since; since="$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')"
      green "  $n  (PID $pid, running $since)"
      tail -2 "$(log_file "$n")" 2>/dev/null | sed 's/^/      /'
    fi
  done
  [ "$found" = 1 ] || echo "  (none)"

  echo
  echo "FINISHED JOBS"
  found=0
  for f in "$JOBS"/*.pid; do
    [ -e "$f" ] || continue
    local n; n="$(basename "$f" .pid)"
    if ! active "$n"; then
      found=1
      local when; when="$(grep '^started' "$(meta_file "$n")" 2>/dev/null | cut -d' ' -f2-)"
      echo "  $n  (started $when)"
      tail -1 "$(log_file "$n")" 2>/dev/null | sed 's/^/      /'
    fi
  done
  [ "$found" = 1 ] || echo "  (none)"
}

# --------------------------------------------------------------------------
cmd_follow() {
  local n="${1:-}"
  if [ -z "$n" ]; then
    for f in "$JOBS"/*.pid; do
      [ -e "$f" ] || continue
      local c; c="$(basename "$f" .pid)"
      if active "$c"; then n="$c"; break; fi
    done
  fi
  [ -n "$n" ] || { red "No active job."; exit 1; }
  echo "Following '$n'. Ctrl-C to stop watching (the job carries on)."
  echo
  tail -f "$(log_file "$n")"
}

# --------------------------------------------------------------------------
cmd_stop() {
  local n="${1:-}"
  if [ -z "$n" ]; then
    echo "Which job? The active ones are:"
    cmd_status
    exit 2
  fi
  active "$n" || { yellow "The job '$n' is not running."; exit 0; }
  local pid; pid="$(cat "$(pid_file "$n")")"
  # SIGTERM to the group: the jobs save their checkpoint and close
  kill -TERM "-$(ps -o pgid= -p "$pid" | tr -d ' ')" 2>/dev/null || kill -TERM "$pid"
  sleep 3
  if active "$n"; then
    yellow "It did not stop gracefully; killing it."
    kill -KILL "-$(ps -o pgid= -p "$pid" | tr -d ' ')" 2>/dev/null || kill -KILL "$pid"
  fi
  green "Stopped '$n'. Resume with:  ./run.sh resume $n"
}

# --------------------------------------------------------------------------
cmd_resume() {
  local n="${1:-}"; shift || true
  [ -n "$n" ] || { red "Resume which job?"; exit 2; }
  case "$n" in
    hunt)
      "$0" launch hunt --resume "$@"
      ;;
    snapshot)
      # the script is idempotent: restarting is safe
      "$0" launch snapshot
      ;;
    *)
      red "The job '$n' has no checkpoint to restart from."
      echo "Launch it again from the beginning with:  ./run.sh launch $n"
      exit 1 ;;
  esac
}

# --------------------------------------------------------------------------
case "${1:-}" in
  estimate) shift; cmd_estimate "$@" ;;
  launch)   shift; cmd_launch "$@" ;;
  status)   shift; cmd_status ;;
  watch)    shift; cmd_watch "$@" ;;
  follow)   shift; cmd_follow "$@" ;;
  stop)     shift; cmd_stop "$@" ;;
  resume)   shift; cmd_resume "$@" ;;
  ""|-h|--help|help) usage ;;
  *) red "Unknown command: $1"; echo; usage; exit 2 ;;
esac
