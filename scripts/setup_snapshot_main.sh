#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Prepara un second snapshot dell'archive, preso da un commit FISSO di `main`.
#
# PERCHE'
# Il tag di benchmark `bench-v1-lean4.27.0` e' del 2026-05-06, cioe' proprio
# alla data di cut dell'addestramento di claude-opus-5 (maggio 2026). Ogni
# dimostrazione contenuta in quel tag era quindi pubblica su GitHub before
# dell'addestramento: calibrare un agente su quei problems misura also quanto
# il model ricorda, non only quanto sa dimostrare.
#
# Su `main` ci sono 548 file di problems added after il 1 giugno 2026. Quelli
# sono materiale post-cutoff.
#
# Il commit e' FISSO: `main` si muove, e un benchmark che si muove non e' un
# benchmark. Cambiarlo va fatto consapevolmente modificando COMMIT_MAIN qui.
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT="$ROOT/external"

#: Commit fisso del branch main. Scelto il 2026-09-10.
COMMIT_MAIN="0a8b856c"
LEAN_MAIN="v4.33.1"

SNAP="$EXT/fc-main"
EXPORT_MAIN="$EXT/lean4export-433"

export PATH="$HOME/.elan/bin:$PATH"

step() { echo; echo "=============================================================="; echo "  $*"; echo "=============================================================="; }

step "0/6  Controlli preliminari"
LIBERI=$(df -g "$ROOT" | tail -1 | awk '{print $4}')
echo "  spazio libero: ${LIBERI} GB"
if [ "$LIBERI" -lt 25 ]; then
  echo "  ERROR: servono almeno 25 GB liberi, ce ne sono ${LIBERI}."
  exit 1
fi

step "1/6  Worktree del commit $COMMIT_MAIN"
# Un worktree condivide la folder .git con il clone esistente: risparmia
# circa un gigabyte e il tempo di un second clone.
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

step "3b/6  Disattivazione della libreria a doppio glob"
# Il branch `main` dichiara DUE librerie che compilano gli stessi file nella
# stessa folder di build: `FormalConjectures` (con `google.answer` al value
# predefinito `alwaysTrue`) e `FormalConjecturesAnswerPostpone` (con
# `postpone`). Gli .olean si sovrascrivono a vicenda, quindi l'statement
# elaborato di un problem con `answer(sorry)` cambia second l'ULTIMO command
# di build eseguito: `lake build FormalConjectures` da' `True ↔ P`,
# `lake build <singolo module>` da' `sorryAx ↔ P`. Un giudice non puo' lavorare
# su un target che si muove, quindi la seconda libreria viene commentata.
# Serve alla CI di upstream per un controllo secondario, non alla check.
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
  echo "  gia' disattivata (o upstream l'ha rimossa)"
fi

step "4/6  Compilazione dell'archive (MOLTO LUNGO)"
# Si lasciano 2 core liberi su 12, come chiesto.
# `lake` di Lean 4.33 non accetta `-j`: si usa la variabile d'environment, che
# funziona su entrambe le versioni. Si lasciano 2 core liberi su 12.
( cd "$SNAP" && LEAN_NUM_THREADS=10 lake build 2>&1 | tail -25 )

step "5/6  lean4export compilato con Lean $LEAN_MAIN"
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
echo "SNAPSHOT PRONTO. Per usarlo:"
echo "  export FCS_ARCHIVE=$SNAP"
echo "  export FCS_LEAN4EXPORT=$EXPORT_MAIN/.lake/build/bin/lean4export"
echo "  export FCS_INDEX=$ROOT/verifier/problem_index_main.json"
