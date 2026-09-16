#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Installa da zero tutto l'environment del progetto.
# Idempotente: si puo' rieseguire senza danni.
#
# Uso:  bash scripts/setup.sh
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT="$ROOT/external"
BIN="$ROOT/tools/bin"

# --- Versioni bloccate -----------------------------------------------------
# Il tag di benchmark decide TUTTO il resto: fix_ la versione di Lean.
FC_TAG="bench-v1-lean4.27.0"
LEAN_VERSION="v4.27.0"

# comparator: usiamo l'last_one versione. NON deve girare sulla stessa versione
# di Lean del progetto (vedi docs/02-verifier.md), ma deve essere recente
# abbastanza da capire il format_ di export current e da supportare i
# "buchi di definition" (definition_names), che ci servono per answer( ).
COMPARATOR_REV="2312244"

# lean4export: il source_text e' quello recente (format_ di export compatibile con
# comparator) MA compilato con Lean 4.27.0, perche' deve leggere gli .olean
# dell'archive, che sono legati alla versione di Lean.
LEAN4EXPORT_REV="master"

step() { echo; echo "==============================================================="; echo "  $*"; echo "==============================================================="; }

# --- 1. elan (gestore di versioni di Lean) ---------------------------------
step "1/7  elan + Lean"
if ! command -v elan >/dev/null 2>&1; then
  export PATH="$HOME/.elan/bin:$PATH"
fi
if ! command -v elan >/dev/null 2>&1; then
  echo "Installo elan dal sito ufficiale..."
  curl -sSf https://elan.lean-lang.org/elan-init.sh -o /tmp/elan-init.sh
  sh /tmp/elan-init.sh -y --default-toolchain stable
  export PATH="$HOME/.elan/bin:$PATH"
fi
elan toolchain install "leanprover/lean4:$LEAN_VERSION"
elan --version

# --- 2. archive dei problems ----------------------------------------------
step "2/7  formal-conjectures @ $FC_TAG"
mkdir -p "$EXT"
if [ ! -d "$EXT/formal-conjectures/.git" ]; then
  git clone https://github.com/google-deepmind/formal-conjectures.git "$EXT/formal-conjectures"
fi
git -C "$EXT/formal-conjectures" fetch --tags --quiet
git -C "$EXT/formal-conjectures" checkout --quiet "$FC_TAG"
test "$(cat "$EXT/formal-conjectures/lean-toolchain")" = "leanprover/lean4:$LEAN_VERSION" \
  || { echo "ERRORE: il tag richiede un Lean diverso da $LEAN_VERSION"; exit 1; }

step "3/7  Cache di Mathlib + compilazione dell'archive (LUNGO: ~30-60 min)"
( cd "$EXT/formal-conjectures" && lake exe cache get && lake build )

# --- 3. lean4export ---------------------------------------------------------
step "4/7  lean4export (compilato con Lean $LEAN_VERSION)"
if [ ! -d "$EXT/lean4export/.git" ]; then
  git clone https://github.com/leanprover/lean4export.git "$EXT/lean4export"
fi
git -C "$EXT/lean4export" fetch --quiet
if [ ! -d "$EXT/lean4export-427" ]; then
  git -C "$EXT/lean4export" worktree add "$EXT/lean4export-427" "$LEAN4EXPORT_REV"
fi
echo "leanprover/lean4:$LEAN_VERSION" > "$EXT/lean4export-427/lean-toolchain"
( cd "$EXT/lean4export-427" && lake build lean4export )

# --- 4. comparator ----------------------------------------------------------
step "5/7  comparator @ $COMPARATOR_REV"
if [ ! -d "$EXT/comparator/.git" ]; then
  git clone https://github.com/leanprover/comparator.git "$EXT/comparator"
fi
git -C "$EXT/comparator" fetch --quiet
git -C "$EXT/comparator" checkout --quiet "$COMPARATOR_REV"
( cd "$EXT/comparator" && lake build comparator )

# --- 5. environment Python -----------------------------------------------------
step "6/7  Ambiente Python isolated (.venv)"
if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install --quiet --upgrade pip
"$ROOT/.venv/bin/pip" install --quiet -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" -c "import pytest, anthropic; print('  pytest', pytest.__version__, '| anthropic', anthropic.__version__)"

# --- 6. check finale -----------------------------------------------------
step "7/7  Controllo dei binari"
for f in "$EXT/comparator/.lake/build/bin/comparator" \
         "$EXT/lean4export-427/.lake/build/bin/lean4export" \
         "$BIN/landrun"; do
  if [ -x "$f" ]; then echo "  OK  $f"; else echo "  MANCANTE  $f"; exit 1; fi
done
echo
echo "Ambiente ready."
echo "Prossimi steps:"
echo "  ./.venv/bin/python verifier/index.py --build   # costruisce l\x27indice dei problems"
echo "  ./.venv/bin/python -m pytest tests/ -v         # esegue i test del verifier"
