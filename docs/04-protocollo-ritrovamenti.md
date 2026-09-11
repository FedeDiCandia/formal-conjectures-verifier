# Protocollo per ogni ritrovamento

Da applicare **prima** di dire a chiunque che si è trovato qualcosa, e prima di
crederci.

La ragione è semplice: in questo campo, un controesempio facile a un problema
famoso quasi sempre significa che **la formalizzazione non dice quello che
sembra dire**, non che il problema sia caduto. I problemi di questo archivio
sono aperti da decenni e molti sono stati verificati al computer fino a soglie
enormi. Se il nostro programma trova un controesempio in dieci minuti, l'ipotesi
di gran lunga più probabile è che l'errore sia nostro.

Il protocollo serve a scoprire di quale caso si tratta, nell'ordine che scarta
prima le ipotesi più probabili.

---

## Passo 1 — Ricontrollo con un programma indipendente

**Cosa fare:** riscrivere il controllo da zero, senza guardare il programma che
ha prodotto il ritrovamento, possibilmente con una strategia diversa (per
esempio: se il primo usava aritmetica modulare, il secondo usi numeri interi
espliciti; se il primo usava una libreria, il secondo la eviti).

**Perché:** un errore di programmazione si ripete identico se si rilegge lo
stesso codice. Non si ripete se il codice è scritto un'altra volta.

**Criterio:** se i due programmi non concordano, il ritrovamento **decade**.
Va capito quale dei due sbaglia, ma intanto non c'è nessun ritrovamento.

---

## Passo 2 — Confronto della formalizzazione con la fonte

**Cosa fare:** leggere l'enunciato Lean dell'archivio accanto all'enunciato
originale del problema (nel docstring c'è sempre il link alla fonte) e
chiedersi, riga per riga, se dicono la stessa cosa. Attenzione particolare a:

| trappola | esempio |
|---|---|
| quantificatore su un insieme più grande del dovuto | `∀ n : ℕ` quando la fonte dice "per ogni intero positivo" e il caso `n = 0` è degenere |
| ipotesi mancante | la fonte richiede che l'insieme sia infinito, la formalizzazione no |
| verso della disuguaglianza | `≤` al posto di `<` |
| convenzione diversa | in Mathlib `Nat.Prime 1` è falso, altrove a volte no; la sottrazione fra naturali tronca a zero |
| `answer(sorry)` che diventa `True` | l'archivio afferma che la risposta è "sì": vedi [docs/01](01-archivio-formal-conjectures.md) |

**Perché:** è il caso più frequente in assoluto. L'archivio stesso lo dichiara
nel suo README: *"Subtle inaccuracies can arise where the formal statement might
not perfectly capture the nuances of the original conjecture."*

**Criterio:** se l'enunciato Lean è più debole dell'originale, o ha perso
un'ipotesi, il caso è **FORMALIZZAZIONE ERRATA**. È comunque un risultato utile,
da segnalare all'archivio — ma non è la soluzione di un problema aperto.

---

## Passo 3 — Ricerca dello stato del problema

**Cosa fare:** cercare online (solo lettura) il problema per nome e per numero,
e stabilire:

- fino a quale soglia è già stato verificato al computer;
- se il caso trovato è già noto in letteratura;
- se esistono risultati parziali che escludono proprio quel caso.

**Perché:** la maggior parte di questi problemi è stata passata al setaccio da
persone con più tempo e macchine più grandi. Se un controesempio sta sotto la
soglia già verificata da altri, **non è un controesempio**: è un errore nostro,
e il passo 1 o il passo 2 devono spiegarlo.

**Criterio:** se il caso è sotto la soglia già verificata, si torna al passo 1.
Se è già noto in letteratura, il caso è **GIÀ NOTO**.

---

## Passo 4 — Verifica in Lean

**Cosa fare:** scrivere la dimostrazione Lean del controesempio e sottoporla al
verificatore.

- Se il problema è `∃ x, P x`, si dimostra l'enunciato **così com'è**:
  ```bash
  ./.venv/bin/python verifier/verify.py NOME file.lean
  ```
- Se il problema è `True ↔ ∀ n, P n` e abbiamo un controesempio, si dimostra la
  **sfida negata**:
  ```bash
  ./.venv/bin/python verifier/verify.py NOME file.lean --confutazione
  ```

**Perché:** finché non c'è una dimostrazione che il verificatore accetta, non
c'è niente. Un numero che sembra un controesempio non è un controesempio finché
Lean non lo conferma.

**Criterio:** se il verificatore accetta, e i passi 1-3 sono stati superati, il
caso è **CANDIDATO NUOVO**.

---

## Le tre classificazioni

| esito | significato | cosa farne |
|---|---|---|
| **FORMALIZZAZIONE ERRATA** | l'enunciato Lean non cattura il problema originale | segnalare all'archivio; non è matematica nuova |
| **GIÀ NOTO** | il fatto è in letteratura | annotarlo; conferma che il sistema funziona |
| **CANDIDATO NUOVO** | ha superato tutti e quattro i passi | **non è ancora un risultato.** Serve la lettura di un matematico competente nell'area. Il verificatore garantisce che la dimostrazione Lean è corretta, non che l'enunciato Lean sia la congettura |

---

## Cosa NON fare

- Non pubblicare, non aprire issue, non scrivere a nessuno prima di aver
  completato tutti e quattro i passi **e** aver fatto leggere il risultato a una
  persona.
- Non saltare il passo 1 perché "il programma è semplice". I programmi semplici
  sbagliano come gli altri.
- Non considerare la verifica di Lean sufficiente da sola: Lean garantisce che
  la dimostrazione è corretta *rispetto all'enunciato scritto*. Se l'enunciato è
  sbagliato, una dimostrazione corretta non serve a niente.
