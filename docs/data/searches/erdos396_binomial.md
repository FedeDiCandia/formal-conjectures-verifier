# Search: erdos396_binomial

**Problem:** `Erdos396.erdos_396`

**What it looks for:** for each k, the least n with descFactorial(n,k+1) dividing centralBinom(n)

**Known state of the problem:** open

**Is the search conclusive?** No: the form is "for every k there exists n", which
no computation can refute. It serves to gather evidence

## Outcome

| | |
|---|---|
| completed | yes |
| duration | 6329 s |
| position reached | 61 |
| cases examined | 61 |
| entries in the result list | 57 |
| nature of those entries | computed results |

## Results (computed results)

**These are not findings.** This search cannot produce a counterexample: what
follows is material to read, not a refutation.

For every k from 4 to 60, no n up to 20,000 was found with
descFactorial(n,k+1) dividing centralBinom(n). Each entry is evidence, not a
counterexample; the raw list is in `erdos396_binomial-result.json`.
