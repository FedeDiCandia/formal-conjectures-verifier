# Contributi a formal-conjectures (bozze, non inviate)

Tre prove verificate in due file. Niente è stato inviato: né issue, né fork, né pull request.

| cartella | teoremi | righe di prova | stato |
|---|---|---|---|
| `DiophantineTuple/` | `isDiophantineTuple_of_subset`, `noIntegralDiophantineFiveTuple_of_hasUniqueExtensionOfForall` | 1 e 26 | pronta: issue e PR in `PR.md`, patch in `proofs.patch` |
| `Erdos1000/` | `erdos_1000.variants.totient_le` | 35 | **da coordinare con la PR aperta #5837**, che cambia l'enunciato: vedi `PR.md` |

`candidati/` contiene i file autonomi sottoposti al verificatore: quello di `DiophantineTuple` usa
il teorema dell'archivio `isDiophantineTuple_of_subset` al posto del lemma ausiliario scritto
dall'agente, così la PR non introduce un duplicato.

## L'attributo `formal_proof`

Per una prova scritta **dentro** il file dell'archivio l'attributo corretto è **nessuno**. Dal 18
agosto 2026 (PR #4962) un linter avverte quando un teorema con `formal_proof` ha una prova diversa
da `sorry`: `formal_proof` serve a indicare una prova che sta *altrove*, su un enunciato che
nell'archivio resta `sorry`. La stessa PR ha tolto l'attributo da `erdos_316` e `erdos_399`, che
hanno la prova nel file.

L'alternativa, per prove lunghe (CONTRIBUTING.md: oltre 25–50 righe), è lasciare `sorry`, mettere
la prova in una repository propria e aggiungere `formal_proof using lean4 at "<link stabile a un
commit>"`. Le nostre tre prove stanno sotto quella soglia; `totient_le` (35 righe) è al limite.

## Passo 0: già formalizzate altrove?

Controllato il 13 settembre 2026:
- file su `main` identici allo snapshot `0a8b856c`, teoremi ancora `sorry`, nessun commit dal 10 settembre;
- nessuna PR, aperta o chiusa, cita `noIntegralDiophantineFiveTuple` o `isDiophantineTuple_of_subset`;
- per `totient_le`: nessuna PR la dimostra; le prove esterne di Erdős 1000 (plby/lean-proofs,
  Jayyhk/erdos-lean) dimostrano l'enunciato principale, non questa variante. La PR #5837 la tocca
  cambiandone l'enunciato.

I dati grezzi sono in `dati_ricerca/formalizzazioni_controllo_*.json`.

## Prima di inviare (a mano)

1. Firmare il Google CLA (https://cla.developers.google.com/).
2. Aprire la issue (testo in `PR.md`).
3. Fork, ramo, `git apply proofs.patch`, `lake build`.
4. Aprire la PR con il testo di `PR.md`, collegata alla issue.
5. Facoltativo: aggiungersi al file `AUTHORS`.
