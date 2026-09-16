# Search: erdos409_sigma

**Problem:** `Erdos409.erdos_409.variants.sigma_prime_termination`

**What it looks for:** iterates n ↦ σ(n)−1 and looks for orbits that never hit a prime

**Known state of the problem:** open

**Is the search conclusive?** No: it finds SUSPECTS, not counterexamples. An orbit
that does not reach a prime in 200 steps has to be examined by hand

## Outcome

| | |
|---|---|
| completed | yes |
| duration | 5 s |
| position reached | 200001 |
| cases examined | 199999 |
| entries in the result list | 0 |
| nature of those entries | suspects |

## Findings

None. **This is not a failure:** a negative outcome says how far one has looked,
and that is information.

**What is known now:** no n up to 200,000 generates an orbit of n ↦ σ(n)−1 that
avoids the primes for 200 steps.
