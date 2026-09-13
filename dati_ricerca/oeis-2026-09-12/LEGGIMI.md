# Schede OEIS consultate il 12 settembre 2026

Formato testo interno di OEIS (`https://oeis.org/search?q=id:ANNNNNN&fmt=text`), scaricato
con curl, senza modifiche. Servono da prova per le citazioni della nota su A105020:

- `A045917.txt`: riga `%F` con la formula di W. I. Hurt (Sep 11 2021), citata in §7 e in A.4;
- `A105020.txt`: nome, offset `0,2`, commento di M. Hiebl (Jul 15 2007), citato in §2;
- `A064911.txt`: nome (funzione caratteristica dei semiprimi);
- `A228553.txt`, `A350419.txt`: le altre due voci di Hurt che usano A105020.

`A045917.html` è la pagina web della voce, scaricata lo stesso giorno: il testo visibile della
riga di Hurt è `a(n) = Sum_{k=n*(n-1)/2+2..n*(n+1)/2} A064911(A105020(k-1)). - Wesley Ivan Hurt, Sep 11 2021`,
identico alla riga `%F` del formato testo tolti i trattini bassi, che lì indicano il link al nome.
