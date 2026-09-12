# Riduzioni e candidati: che cosa la fase D ha effettivamente prodotto

*Aggiornato il 12 settembre 2026. Materiale grezzo in `runs/informale.json`.*

Questo documento raccoglie l'unica cosa di valore duraturo uscita dalla fase D: non
dimostrazioni di congetture aperte, ma **riduzioni** — «questo problema è aperto
perché implica quest'altro problema, che è aperto da decenni». Una riduzione
corretta è un risultato piccolo ma reale, ed è materiale utile se un giorno si
volesse segnalare qualcosa a chi cura l'archivio o la voce OEIS.

**Come leggere le colonne.** «Riduzione» è quello che il modello afferma. «Stato in
letteratura» è quello che ho verificato io, e la verifica è di due tipi con forza
molto diversa: se la voce OEIS *non* menziona la riduzione, quello è un fatto
accertato su quella voce; se una ricerca in rete non trova niente, quella è **prova
debole** — significa che non l'ho trovata, non che non esista.

**Nessuna di queste riduzioni è stata verificata formalmente.** Sono pagine di
matematica in linguaggio naturale, lette da me e da una seconda chiamata nel ruolo
di revisore severo. Non valgono come dimostrazioni.

---

## 1. Il caso che conta: una congettura che era già stata dimostrata

**`OeisA357513.general_supercongruence`** — [A357513](https://oeis.org/A357513)

> Per ogni intero m ≥ 0, sia u(n) il numeratore di
> ∑_{k=1}^{n} (1/k^{2m+1})·C(n,k)²·C(n+k,k)². Allora u(p−1) ≡ 0 (mod p⁴) per ogni
> primo p, con un numero finito di eccezioni che dipendono da m.

**È l'unico candidato, in tutta la storia di questo progetto, che sia sopravvissuto
alla revisione severa.** L'autore ha dichiarato `PROOF`; il revisore, il cui compito
è rompere, ha risposto `HOLDS`. Costo: **$0,50**, una sola chiamata, effort basso.

E il primo passo del protocollo di [docs/04](04-protocollo-ritrovamenti.md) — *cerca
in letteratura prima di chiamarlo risultato* — ha dato questo:

> **«This conjecture is now proved; see Links. The exceptional primes are exactly the
> primes p for which p − 1 divides 2m + 4 and p does not divide 2m + 7…»**
> — commento di **Ondrej Kutal, 18 luglio 2026**, nella voce A357513

Con due link: la dimostrazione del caso m = 1 di **AlphaProof** (gennaio 2026) e **la
dimostrazione del caso generale, con formalizzazione in Lean**, di Kutal
([github.com/TheSil/A357513_conjecture](https://github.com/TheSil/A357513_conjecture),
luglio 2026).

**Quindi: non è un risultato.** Era già fatto, due mesi prima, da una persona, e
formalizzato. Tre conseguenze, in ordine di importanza:

1. **Il protocollo ha funzionato al primo colpo utile.** Il candidato è stato fermato
   dal controllo in letteratura, non da un'intuizione, e prima di qualunque
   annuncio. È la settima volta in questo progetto che un controllo ferma qualcosa
   che la macchina voleva far passare, e la prima in cui la cosa fermata era *vera*
   invece che sbagliata.
2. **L'etichetta dell'archivio è scaduta.** `general_supercongruence` è marcata
   `@[category research open]` nello snapshot del 10 settembre 2026, ma la voce OEIS
   dice «now proved» dal 18 luglio. È l'ottava etichetta scaduta che troviamo, e
   l'unica trovata *dopo* che il nostro sistema ci aveva lavorato. Segnalabile a chi
   cura `formal-conjectures` (vedi sotto).
3. **Dice qualcosa sulla capacità, che va detto con cautela.** Il modello, in una
   chiamata da cinquanta centesimi a effort basso, ha prodotto una dimostrazione di
   un enunciato che **è vero** e che un essere umano ha dimostrato a luglio. Non ho
   verificato che *la sua* dimostrazione sia corretta, e non posso: il punto debole
   che si è autodichiarato è la contabilità dell'espansione p-adica nel passo 2.
   Ma non è un caso di modello che inventa: ha puntato a un bersaglio vero.

**Il controllo di scadenza l'ho poi fatto su tutte e venti le successioni della fase
D**, confrontando le voci OEIS con le etichette dell'archivio: **una scaduta su
venti**, ed è questa. Le altre diciannove risultano ancora aperte.

---

## 2. Il raccolto: sette problemi su diciannove si riducono a problemi famosi

Il giro completo: **19 problemi, 1 solo sopravvissuto alla revisione** (quello sopra,
già dimostrato), **$3,53** in tutto. Ma l'esito che conta non è il conteggio: è che
in sette risposte su diciannove il modello **nomina il problema famoso** a cui il
nostro «oscuro problema OEIS» si riduce.

### 2a. Problemi che *sono* congetture famose, e non lo sapevamo

Qui non c'è nessuna scoperta: c'è il nostro errore di selezione, documentato. La
riduzione era già scritta nella voce OEIS, e non l'avevo letta.

| problema | che cos'è davvero | dove era già scritto |
|---|---|---|
| **`OeisA103151.conjecture`** | la **congettura di Lemoine** (o di Levy): ogni dispari > 5 è p + 2q con p, q primi | la voce A103151 dice, alla riga di commento: *«This is a stronger conjecture than the Goldbach conjecture»* |
| **`OeisA110835.conjecture`** | la **congettura di Sierpiński del 1958**, nella forza di Legendre/Brocard: primi in intervalli corti vicino a √ | commento di Charles R Greathouse IV, 2010: *«Sierpinski's conjecture (1958) is precisely that a(n) >= n for all n»* |
| **`OeisA231201.conjecture`** | una congettura di **Zhi-Wei Sun**, per cui l'autore offre un premio di $1000 | la voce è di Sun stesso |
| **`OeisA109909.conjecture`** | famiglia Goldbach: esistono primi della forma k(n−k)−1 | verificata fino a 10⁹ (Fiorentini, 2023), nessuna dimostrazione |

**Questa tabella è la spiegazione definitiva del «due candidati su 139 chiamate».**
La lista dei 54 problemi della «famiglia giusta» non era una lista di problemi poco
studiati: era una lista di **Goldbach, Lemoine, Sierpiński e Sun travestiti da
numeri OEIS**. L'agente non consegnava niente perché gli stavamo chiedendo Goldbach.

### 2b. Riduzioni vere, con una verifica mia

**`OeisA105020.conjecture` — è equivalente a Goldbach, dimostrato; nella sostanza già noto** (formula di Hurt in A045917, 2021: vedi [segnalazioni/A105020.md](segnalazioni/A105020.md) §6). **Verificato in Lean** dal nostro verificatore (§5). La bozza di
segnalazione con la dimostrazione completa e tutti i controlli è in
[docs/segnalazioni/A105020.md](segnalazioni/A105020.md).

In breve: sull'antidiagonale c il termine in posizione k vale (k+1)(2c+1−k); gli
indici con un valore dato corrispondono alle sue fattorizzazioni; con i = T_n e
j = T_{n+1} i termini intermedi sono pq con p + q = 2n+2, e pq è semiprimo se e solo se
p e q sono primi.

| direzione | stato |
|---|---|
| l'enunciato ⟹ Goldbach binaria | **dimostrato** |
| Goldbach ⟹ l'enunciato | **dimostrato**, grazie al lemma: le ipotesi forzano i = T_n e j = T_{n+1} |
| il lemma | dimostrato in due casi; identità verificate con sympy; forza bruta per s ≤ 1500; **nessuna coppia non canonica** fra tutti gli indici < 10¹⁰ né fra tutti i valori ≤ 4·10⁹ (9,8 miliardi di casi) |

**Una correzione, già registrata.** In una prima stesura avevo invertito il verso
rigoroso; poi mancava il lemma sulle coppie non canoniche, individuato da Federico come
unico pezzo mancante e ora dimostrato. La formalizzazione dell'archivio è corretta
(`Nat.IsSemiprime n` è `n ≠ 0 ∧ Ω n = 2`); non è formalizzata in Lean la nostra
dimostrazione.

**`OeisA108569.conjecture` — e il problema del totiente di Lehmer.**

| | |
|---|---|
| enunciato | «tutti i termini oltre il primo sono pari», cioè nessun k > 1 dispari con φ(k) = φ(k+φ(k)) |
| riduzione affermata | un tale k primo p forza m = 2p−1 a essere un **numero di Lehmer di indice 2**: composto, senza quadrati, φ(m) \| m−1 con quoziente 2, non divisibile per 3, tutti i fattori primi ≥ 5 e almeno 7 di essi, e p ≡ 1 (mod 24) |
| stato in letteratura | la congettura è di **Farideh Firoozbakht** (luglio 2005). La voce OEIS **non menziona Lehmer** in nessun commento, formula, riferimento o rimando (i soli rimandi sono A005384 e A051487) — *fatto accertato sulla voce*. Una ricerca in rete non trova il collegamento: la letteratura vicina riguarda φ(n) = φ(n+k) e φ(n+k) = Mφ(n), equazioni diverse — *prova debole*. Il problema di Lehmer è aperto dal 1932; per una soluzione si sa n > 10²⁰ e ω(n) ≥ 14 (Cohen–Hagis 1980) |

**`OeisA101779.conjecture` — e la congettura di Dickson.** Il modello dà una
dimostrazione **condizionale completa**: l'enunciato è un'istanza genuina della
congettura di Dickson, con la verifica di ammissibilità fatta per esteso (che è,
dice, la sola parte davvero elementare). La voce OEIS non nomina Dickson nei
commenti. Anche qui: *fatto accertato sulla voce, prova debole sulla letteratura* —
e per un esperto questa riduzione è probabilmente folklore.

## 3. Che cosa si potrebbe segnalare, e a chi

Niente è stato inviato a nessuno. Le tre cose che avrebbero un destinatario:

| cosa | a chi | perché è utile a loro |
|---|---|---|
| l'etichetta scaduta di `general_supercongruence` | chi cura `formal-conjectures` (Google DeepMind), come *issue* | un problema marcato aperto che è stato dimostrato e formalizzato da due mesi; il loro stesso file cita già la prova AlphaProof del caso m = 1 |
| le sette etichette scadute trovate prima | stesso destinatario, stessa *issue* | sono nel registro del progetto con la fonte di ciascuna |
| la riduzione A108569 → Lehmer | un commento alla voce OEIS A108569 | spiegherebbe *perché* la congettura di Firoozbakht è difficile, cosa che la voce oggi non dice |
| che A105020 è **equivalente** a Goldbach, non un'analogia | un commento alla voce OEIS A105020, e una segnalazione all'archivio | la voce dice «a Goldbach Conjecture *for this sequence*»; l'equivalenza è dimostrata, con i testi pronti in [segnalazioni/A105020.md](segnalazioni/A105020.md) |
| la riduzione A101779 → Dickson | un commento alla voce OEIS A101779 | idem, ma è la meno originale: per un esperto è probabilmente folklore |

**La terza va trattata con più prudenza delle altre due.** Le prime due sono fatti
verificabili in un minuto da chiunque (una data e un link). La terza è una catena di
ragionamento non formalizzata, prodotta da un modello e controllata da me, che non
sono matematico. Prima di proporla a OEIS servirebbe che **una persona competente la
leggesse** — ed è precisamente la strada E del piano, chiedere aiuto umano come
parte del metodo.
