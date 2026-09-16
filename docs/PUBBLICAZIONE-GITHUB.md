# Pubblicare il progetto su GitHub

Preparato il 15 settembre 2026. I comandi li esegui tu: `gh` e `git push` sono negati qui dentro.

## Stato: che cosa è già fatto

- `.gitignore` più stretto (`.venv-*/`, `.pytest_cache/`, `.env.*`, `*.pem`, `id_rsa*`, `**/.DS_Store`);
- `.env.esempio` ripristinato, in inglese, senza chiavi;
- `README.md` in inglese come pagina pubblica, `README.it.md` per l'italiano;
- `LICENSE` (Apache 2.0, testo canonico) e `NOTICE` (attribuzioni file per file);
- il PDF della nota su A105020, che era tracciato ma sparito dal disco, ripristinato.

## Controlli fatti prima (esiti)

| controllo | esito |
|---|---|
| `.env` tracciato o in un commit | **mai**, in nessuno dei 132 commit |
| chiavi API, token, password in tutta la storia | **nessuna**; solo il segnaposto `sk-ant-metti-qui-la-tua-chiave` di `.env.esempio` |
| cartelle grandi escluse | sì: `external/` (37 GB), `runs/` (555 MB), i due virtualenv (388 MB) |
| peso da scaricare (`.git` impacchettato) | **4,1 MB** |
| peso della copia di lavoro | **12,8 MB** (di cui 6,0 MB gli indici dei problemi e 5,3 MB i dati di ricerca) |

## Decisioni che restano a te

1. **L'email dei commit.** Tutti e 132 hanno come autore `Federico Di Candia
   <dicandia.fe@gmail.com>`: pubblicando, l'indirizzo diventa visibile. Se non lo vuoi, la
   riscrittura va fatta **prima** del push (`git filter-repo --mail-map`), non dopo.
2. **Il tuo secondo indirizzo email** compariva una volta in `INVIO.md`: tolto il 15 settembre.
3. **`/Users/fededicandia`** compare in 8 file tracciati (28 volte), quasi tutti registri in `docs/dati/`.
4. **I dati di terzi in `dati_ricerca/`**: le tabelle di Brouwer (362 codici più due pagine) non
   hanno licenza dichiarata, quindi dal 15 settembre **non sono più versionate** (restano sul
   disco; `ricerca/riproduci.py` le riscarica). L'email privata nell'intestazione di un codice è
   stata tolta. Le voci OEIS sono CC BY-SA 4.0: si ridistribuiscono citando la fonte, come fa
   `NOTICE`. Per rimetterle dentro:
   ```bash
   git rm -r --cached dati_ricerca/codici dati_ricerca/Andw.html dati_ricerca/binary-1.html
   printf 'dati_ricerca/codici/\ndati_ricerca/Andw.html\ndati_ricerca/binary-1.html\n' >> .gitignore
   git commit -m "Dati di Brouwer non ridistribuiti: li scarica ricerca/riproduci.py"
   ```
   I file restano sul disco; `ricerca/riproduci.py` li riscarica da `aeb.win.tue.nl`. La copia di
   lavoro scende da 12,8 a circa 9 MB. (Restano però nella storia: per toglierli anche da lì
   serve `git filter-repo`.)

## Prima: sbloccare git

Un aggiornamento di Xcode ha invalidato la licenza, e `git` si rifiuta di partire. Una delle due:

```bash
sudo xcodebuild -license accept              # accetta la licenza Xcode
# oppure, se non usi Xcode per compilare:
sudo xcode-select -s /Library/Developer/CommandLineTools
```

## 1. Creare il repository e fare il push (con gh)

```bash
cd /Users/fededicandia/Documents/Math
git status --short                            # deve essere vuoto
gh auth status                                # deve dire: account FedeDiCandia

gh repo create formal-conjectures-solver \
  --public \
  --source=. \
  --remote=origin \
  --description "A Lean 4 verifier and an agent for the formal-conjectures archive: machine-checked proofs, measurements, and what did not work" \
  --push
```

Un solo comando: crea il repository, aggiunge il remote `origin` e spinge `main`.
Per guardarlo prima che lo veda qualcun altro, metti `--private` al posto di `--public`; poi:

```bash
gh repo edit FedeDiCandia/formal-conjectures-solver \
  --visibility public --accept-visibility-change-consequences
```

## 2. Senza gh

Crea il repository su <https://github.com/new> con il nome `formal-conjectures-solver`,
**senza** spuntare README, .gitignore o licenza (ci sono già: altrimenti il push va in conflitto).
Poi:

```bash
cd /Users/fededicandia/Documents/Math
git remote add origin https://github.com/FedeDiCandia/formal-conjectures-solver.git
git branch -M main
git push -u origin main
```

## 3. Dopo il push, tre verifiche

```bash
gh repo view FedeDiCandia/formal-conjectures-solver --web   # README, licenza riconosciuta
gh api repos/FedeDiCandia/formal-conjectures-solver/contents/.env    # deve dare 404
git ls-remote origin                                        # main è lì
```

Se il nome del repository sarà diverso, cambia anche l'URL nel README:

```bash
sed -i '' 's#FedeDiCandia/formal-conjectures-solver#FedeDiCandia/NUOVO-NOME#' README.md
git commit -am "README: URL del repository"
```

## Non c'entra con questo push

Le due pull request su `google-deepmind/formal-conjectures` sono un'altra cosa, e i loro comandi
stanno in [contributi/formal-conjectures/INVIO.md](contributi/formal-conjectures/INVIO.md).
Il remote `origin` di questo repository non ha niente a che vedere con il fork lì.
