#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Prepare a second snapshot of the archive, taken from a FIXED commit of `main`.
#
# PERCHE'
# The benchmark tag `bench-v1-lean4.27.0` is dated 2026-05-06, exactly at
# claude-opus-5's training cutoff (May 2026). Every proof in that tag was
# therefore public on GitHub before training: calibrating an agent on those
# problems measures how much the model remembers as well as how much it can
# prove.
#
# On `main` there are 548 problem files added after 1 June 2026. Those are
# post-cutoff material.
#
# The commit is FIXED: `main` moves, and a benchmark that moves is not a
# benchmark. Cambiarlo va fatto consapevolmente modificando COMMIT_MAIN qui.
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT="$ROOT/external"

#: Fixed commit of the main branch. Chosen on 2026-09-10.
COMMIT_MAIN="0a8b856c"
LEAN_MAIN="v4.33.1"

SNAP="$EXT/fc-main"
EXPORT_MAIN="$EXT/lean4export-433"

export PATH="$HOME/.elan/bin:$PATH"

step() { echo; echo "=============================================================="; echo "  $*"; echo "=============================================================="; }

step "0/6  Controlli preliminari"
FREE_GB=$(df -g "$ROOT" | tail -1 | awk '{print $4}')
echo "  free space: ${FREE_GB} GB"
if [ "$FREE_GB" -lt 25 ]; then
  echo "  ERROR: at least 25 GB free are needed, there are ${FREE_GB}."
  exit 1
fi

step "1/6  Worktree del commit $COMMIT_MAIN"
# A worktree shares the .git directory with the existing clone: it saves about
# a gigabyte and the time of a second clone.
if [ ! -d "$SNAP" ]; then
  git -C "$EXT/formal-conjectures" fetch --quiet origin main
  git -C "$EXT/formal-conjectures" worktree add --detach "$SNAP" "$COMMIT_MAIN"
fi
echo "  commit: $(git -C "$SNAP" rev-parse --short HEAD)"
RICHIESTO=$(cat "$SNAP/lean-toolchain")
echo "  toolchain richiesto: $RICHIESTO"
if [ "$RICHIESTO" != "leanprover/lean4:$LEAN_MAIN" ]; then
  echo "  ATTENZIONE: mi aspettavo leanprover/lean4:$LEAN_MAIN"
fi

step "2/6  Toolchain Lean $LEAN_MAIN"
elan toolchain install "leanprover/lean4:$LEAN_MAIN" 2>&1 | tail -2

step "3/6  Cache di Mathlib (LUNGO)"
( cd "$SNAP" && lake exe cache get 2>&1 | tail -3 )

step "3b/6  Disabling the double-glob library"
# The `main` branch declares TWO libraries that compile the same files into the
# same build directory: `FormalConjectures` (with `google.answer` at its default
# `alwaysTrue`) and `FormalConjecturesAnswerPostpone` (with `postpone`). The
# .olean files overwrite each other, so the elaborated statement of a problem
# with `answer(sorry)` changes according to the LAST build command:
# di build eseguito: `lake build FormalConjectures` da' `True ↔ P`,
# `lake build <a single module>` gives `sorryAx ↔ P`. A judge cannot work against
# a moving target, so the second library is commented out.
# It serves upstream's CI for a secondary check, not the verification.
if grep -q '^name = "FormalConjecturesAnswerPostpone"' "$SNAP/lakefile.toml"; then
  python3 - "$SNAP/lakefile.toml" <<'PYEOF'
import sys
from pathlib import Path
f = Path(sys.argv[1])
lines = f.read_text(encoding="utf-8").split("\n")
i_nome = next(i for i, r in enumerate(lines) if "FormalConjecturesAnswerPostpone" in r)
i_inizio = max(i for i in range(i_nome) if lines[i].strip() == "[[lean_lib]]")
i_fine = next(i for i in range(i_nome, len(lines)) if lines[i].startswith("weak.google.answer"))
lines[i_inizio:i_fine + 1] = ["# disattivata dallo snapshot: vedi scripts/setup_snapshot_main.sh"] + \
    ["# " + r if r.strip() else "#" for r in lines[i_inizio:i_fine + 1]]
f.write_text("\n".join(lines), encoding="utf-8")
print("  libreria a doppio glob disattivata")
PYEOF
else
  echo "  already disabled (or upstream removed it)"
fi

step "4/6  Building the archive (VERY LONG)"
# 2 of the 12 cores are left free, as asked.
# Lean 4.33's `lake` does not accept `-j`: the environment variable is used, which
# works on both versions. 2 of the 12 cores are left free.
( cd "$SNAP" && LEAN_NUM_THREADS=10 lake build 2>&1 | tail -25 )

step "5/6  lean4export built with Lean $LEAN_MAIN"
if [ ! -d "$EXPORT_MAIN" ]; then
  git -C "$EXT/lean4export" worktree add --detach "$EXPORT_MAIN" master
fi
echo "leanprover/lean4:$LEAN_MAIN" > "$EXPORT_MAIN/lean-toolchain"
( cd "$EXPORT_MAIN" && lake build lean4export 2>&1 | tail -5 )

step "6/6  Controllo finale"
for f in "$SNAP/.lake/build/lib/lean" "$EXPORT_MAIN/.lake/build/bin/lean4export"; do
  if [ -e "$f" ]; then echo "  OK  $f"; else echo "  MANCANTE  $f"; exit 1; fi
done
echo
echo "  olean compiled: $(find "$SNAP/.lake/build/lib/lean/FormalConjectures" -name '*.olean' 2>/dev/null | wc -l)"
echo "  spazio occupato: $(du -sh "$SNAP" | cut -f1)"
echo
echo "SNAPSHOT READY. To use it:"
echo "  export FCS_ARCHIVE=$SNAP"
echo "  export FCS_LEAN4EXPORT=$EXPORT_MAIN/.lake/build/bin/lean4export"
echo "  export FCS_INDEX=$ROOT/verifier/problem_index_main.json"
