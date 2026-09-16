# OEIS entries consulted on 12 September 2026

OEIS's internal text format (`https://oeis.org/search?q=id:ANNNNNN&fmt=text`), fetched
with curl, unmodified. They are the evidence for the citations in the A105020 note:

- `A045917.txt`: the `%F` line with W. I. Hurt's formula (Sep 11 2021), cited in §7 and A.4;
- `A105020.txt`: name, offset `0,2`, M. Hiebl's comment (Jul 15 2007), cited in §2;
- `A064911.txt`: name (the characteristic function of the semiprimes);
- `A228553.txt`, `A350419.txt`: the other two Hurt entries that use A105020.

`A045917.html` is the entry's web page, fetched the same day: the visible text of
Hurt's line is
`a(n) = Sum_{k=n*(n-1)/2+2..n*(n+1)/2} A064911(A105020(k-1)). - Wesley Ivan Hurt, Sep 11 2021`,
identical to the `%F` line of the text format once the underscores — which mark the
link to the name there — are removed.

These files are OEIS content, licensed CC BY-SA 4.0. See NOTICE.
