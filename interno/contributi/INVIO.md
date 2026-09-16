# Inviare le due pull request (li esegui tu)

Preparato il 14 settembre 2026. Tutto quello che non pubblica niente è già fatto, in
`external/pr-formal-conjectures`:

- clone di `google-deepmind/formal-conjectures`, remote `upstream`;
- branch `prove-diophantine-tuple-textbook` e `prove-erdos-1000-totient-le`, ciascuno partito
  dall'ultimo `main`, con la patch applicata, `lake build` del modulo toccato e un commit locale;
- testi delle PR in `DiophantineTuple/pr_body.md` e `Erdos1000/pr_body.md`;
- registro della preparazione in `runs/pr_preparazione.log`.

Restano solo le operazioni che pubblicano: il fork, il push e l'apertura delle PR.

**Verificato il 14 settembre, 16:27–16:40:**
- ultimo `main` = `62f56e8`; i due file sono identici alle basi delle patch; Lean, Mathlib,
  `FormalConjecturesUtil` e `lakefile.toml` identici a quelli con cui le prove sono state verificate;
- branch `prove-diophantine-tuple-textbook` = commit `17ba40e` (1 file, +29 −3);
  branch `prove-erdos-1000-totient-le` = commit `26411c3` (1 file, +35 −1); entrambi partono da `62f56e8`;
- `lake build` di ciascun modulo, ricompilato davvero: **nessun avviso** (con le opzioni di
  `lakefile.toml`, che spengono gli avvisi `sorry` e accendono i linter dell'archivio);
- `#print axioms`: solo `propext`, `Classical.choice`, `Quot.sound`;
- nella copia locale il push verso `upstream` è disattivato apposta
  (`git remote set-url --push upstream DISABLED-…`): si pubblica solo sul remote `fork`.

## 0. Due controlli prima di pubblicare

**L'email dei commit.** I commit locali hanno come autore `Federico Di Candia
<l'email dei tuoi commit>` (la tua configurazione globale di git). Il controllo CLA di Google
guarda l'email dei commit: deve essere quella con cui hai firmato il CLA e deve essere associata
al tuo account GitHub. Se non lo è:

```bash
cd /Users/fededicandia/Documents/Math/external/pr-formal-conjectures
git config user.email "EMAIL-DEL-CLA"
for b in prove-diophantine-tuple-textbook prove-erdos-1000-totient-le; do
  git checkout "$b" && git commit --amend --no-edit --reset-author
done
```

**La riga `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`** nei messaggi dei commit.
Dichiara l'aiuto dell'IA anche nella storia di git. Il controllo CLA di Google considera anche i
co-autori indicati così: se segnala che un co-autore non ha firmato, togli la riga (la
dichiarazione resta nel testo della PR) e rifai il push:

```bash
git checkout NOME-DEL-BRANCH
git commit --amend          # cancella la riga Co-Authored-By e salva
git push --force-with-lease fork NOME-DEL-BRANCH
```

## 1. Fork e remote

```bash
cd /Users/fededicandia/Documents/Math/external/pr-formal-conjectures
gh auth status                       # deve dire: Logged in to github.com account FedeDiCandia
gh auth setup-git                    # git userà le credenziali di gh per il push
gh repo fork google-deepmind/formal-conjectures --clone=false
git remote add fork https://github.com/FedeDiCandia/formal-conjectures.git
git remote -v                        # upstream = google-deepmind, fork = FedeDiCandia
```

## 2. Controllo finale di ciascun branch

```bash
git log --oneline -1 prove-diophantine-tuple-textbook
git show --stat prove-diophantine-tuple-textbook      # un solo file: Wikipedia/DiophantineTuple.lean
git log --oneline -1 prove-erdos-1000-totient-le
git show --stat prove-erdos-1000-totient-le           # un solo file: ErdosProblems/1000.lean
```

Se nel frattempo `main` è andato avanti e GitHub segnala conflitti (per esempio se viene unita
la PR #4688, «modulize FormalConjectures/», che tocca anche `1000.lean`):

```bash
git fetch upstream
git checkout NOME-DEL-BRANCH && git rebase upstream/main
lake build FormalConjectures.Wikipedia.DiophantineTuple        # o 'FormalConjectures.ErdosProblems.«1000»'
git push --force-with-lease fork NOME-DEL-BRANCH
```

## 3. Push e apertura delle PR

**DiophantineTuple (issue #5992):**

```bash
git push -u fork prove-diophantine-tuple-textbook
gh pr create --repo google-deepmind/formal-conjectures --base main \
  --head FedeDiCandia:prove-diophantine-tuple-textbook \
  --title "feat(Wikipedia/DiophantineTuple): prove two textbook statements" \
  --body-file /Users/fededicandia/Documents/Math/docs/contributi/formal-conjectures/DiophantineTuple/pr_body.md
```

**Erdos1000 (issue #5993):**

```bash
git push -u fork prove-erdos-1000-totient-le
gh pr create --repo google-deepmind/formal-conjectures --base main \
  --head FedeDiCandia:prove-erdos-1000-totient-le \
  --title 'feat(ErdosProblems/1000): prove `erdos_1000.variants.totient_le`' \
  --body-file /Users/fededicandia/Documents/Math/docs/contributi/formal-conjectures/Erdos1000/pr_body.md
```

Attenzione: con `--title` e `--body-file` la PR **viene aperta subito**, senza chiedere conferma.
Per rivederla prima, sostituisci `--title … --body-file …` con `--web`: si apre la pagina di
creazione nel browser, incolli il titolo e il testo di `pr_body.md` e premi tu il pulsante.
Se `gh pr create --help` elenca `--dry-run`, puoi anche provarla senza crearla.

**Senza `gh`:** fai il fork dal pulsante «Fork» su GitHub, poi `git remote add fork …` come sopra,
il `git push`, e apri le PR da
`https://github.com/google-deepmind/formal-conjectures/compare/main...FedeDiCandia:formal-conjectures:NOME-DEL-BRANCH`
incollando il testo del file `pr_body.md`.

## La frase sulla lettura della prova

I testi dichiarano l'aiuto dell'IA e la verifica a macchina, senza «I have read and understood
the proof». Aggiungila in fondo alla sezione «AI assistance» solo se vale per quella prova.
