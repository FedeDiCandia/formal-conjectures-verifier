"""
The search programs, one per problem.

Each program honours the contract in verifier/search.py: it reads the checkpoint,
saves its progress, handles SIGTERM and does not use the network.

Each program starts with a SELF-TEST block that recomputes KNOWN values and stops if
they do not match. A search that starts from a wrong computation produces a false
finding, which is worse than no finding.
"""

# ---------------------------------------------------------------------------
# 1. Euclid numbers with no square factors
# ---------------------------------------------------------------------------
# PROBLEM: EuclidNumbers.euclid_numbers_are_square_free
#   True ↔ ∀ n, Squarefree (Euclid n)      with Euclid n = p_n# + 1
#
# KNOWN STATE (searched on the web on 2026-09-10): whether every Euclid number is
# squarefree is open. No published systematic search for counterexamples was
# found.
#
# HOW IT IS SEARCHED: if p² divides p_n# + 1 then p does not divide p_n#, so p is
# greater than p_n. For each prime p the primorial is computed mod p², multiplying one
# prime q < p at a time, and we watch for it becoming −1 mod p². Cost: about π(p)
# operations per p, that is P²/(2 ln²P) in total. For P = 10^6 that is a couple of
# billion multiplications: hours, not days.
EUCLID = r'''
import json, os, signal, sys, time

def cribro(n):
    """The primes up to n, by the sieve of Eratosthenes."""
    s = bytearray([1]) * (n + 1)
    s[0:2] = b"\x00\x00"
    i = 2
    while i * i <= n:
        if s[i]:
            s[i*i::i] = bytearray(len(s[i*i::i]))
        i += 1
    return [i for i in range(n + 1) if s[i]]

# --- SELF-TEST on known values -------------------------------------------------
# The first Euclid numbers are 3, 7, 31, 211, 2311, 30031, 510511.
expected = [3, 7, 31, 211, 2311, 30031, 510511]
pr = cribro(100)
acc, computed = 1, []
for q in pr[:7]:
    acc *= q
    computed.append(acc + 1)
if computed != expected:
    print(json.dumps({"event": "shakedown_failed",
                      "expected": expected, "calculated": computed}), flush=True)
    sys.exit(1)
# 30031 = 59 * 509: the sixth Euclid number is NOT prime (but it is squarefree)
if 30031 % 59 != 0:
    print(json.dumps({"event": "shakedown_failed", "detail": "30031 = 59*509"}), flush=True)
    sys.exit(1)
print(json.dumps({"event": "shakedown", "result": "passed",
                  "checked": "the first 7 Euclid numbers and the factorisation of 30031"}),
      flush=True)

# --- the search -----------------------------------------------------------------
checkpoint = os.environ["SEARCH_CHECKPOINT"]
state = os.environ["SEARCH_STATE"]
LIMIT = int(os.environ.get("LIMIT_P", "200000"))

index_start = 0
found = []
examined = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    index_start = d.get("position", 0)
    found = d.get("found", [])
    examined = d.get("examined", 0)

primes = cribro(LIMIT)
print(json.dumps({"event": "start", "primi_disponibili": len(primes),
                  "limit": LIMIT, "riparto_da_indice": index_start}), flush=True)

stopped = False
def stop(s, f):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

def salva(i):
    tmp = state + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"position": i, "examined": examined, "found": found,
                   "ultimo_primo": primes[i - 1] if i else None}, f)
    os.replace(tmp, state)

t0 = time.time()
last_warning = t0
for i in range(index_start, len(primes)):
    if stopped:
        break
    p = primes[i]
    p2 = p * p
    acc = 1
    # the primorial mod p^2, one prime q < p at a time
    for j in range(i):          # every prime q < p
        acc = (acc * primes[j]) % p2
        if acc == p2 - 1:       # acc ≡ -1 (mod p^2), that is p^2 | p_n# + 1
            found.append({"p": p, "primorial_index": j + 1,
                            "last_prime_of_the_primorial": primes[j]})
            print(json.dumps({"event": "found",
                              "detail": found[-1]}), flush=True)
    examined += 1
    now = time.time()
    if now - last_warning > 30:
        salva(i + 1)
        print(json.dumps({"event": "progress", "position": i + 1,
                          "examined": examined, "current_prime": p,
                          "seconds": round(now - t0)}), flush=True)
        last_warning = now

salva(min(i + 1, len(primes)))
print(json.dumps({"event": "end", "position": min(i + 1, len(primes)),
                  "examined": examined, "found": len(found),
                  "seconds": round(time.time() - t0)}), flush=True)
'''


# ---------------------------------------------------------------------------
# 2. Erdos 409: does iterating sigma minus one always reach a prime?
# ---------------------------------------------------------------------------
# PROBLEM: Erdos409.erdos_409.variants.sigma_prime_termination
#   True ↔ ∀ n > 1, ∃ i, Prime ((fun x => σ₁(x) - 1)^[i] n)
#
# HOW IT IS SEARCHED: for each n, iterate m ↦ σ(m) − 1 until a prime is met. A
# counterexample is an n whose orbit never meets a prime: either it enters a cycle or
# it grows without bound. A cap on steps and on size is fixed; whatever exceeds it is
# reported as a SUSPECT, not as a counterexample — an important distinction, because
# "I did not find it in a thousand steps" is not "it does not exist".
SIGMA = r'''
import json, os, signal, sys, time

def factorise(n):
    f = {}
    d = 2
    while d * d <= n:
        while n % d == 0:
            f[d] = f.get(d, 0) + 1
            n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        f[n] = f.get(n, 0) + 1
    return f

def sigma(n):
    """Sum of divisors."""
    if n <= 1:
        return n
    s = 1
    for p, e in factorise(n).items():
        s *= (p ** (e + 1) - 1) // (p - 1)
    return s

def is_prime(n):
    if n < 2: return False
    if n < 4: return True
    if n % 2 == 0: return False
    d = 3
    while d * d <= n:
        if n % d == 0: return False
        d += 2
    return True

# --- SELF-TEST on known values -------------------------------------------------
# sigma: 1,3,4,7,6,12,8,15,13,18 for n = 1..10
expected = [1, 3, 4, 7, 6, 12, 8, 15, 13, 18]
computed = [sigma(n) for n in range(1, 11)]
if computed != expected:
    print(json.dumps({"event": "shakedown_failed", "expected": expected,
                      "calculated": computed}), flush=True)
    sys.exit(1)
# sigma(28) = 56 because 28 is perfect
if sigma(28) != 56:
    print(json.dumps({"event": "shakedown_failed", "detail": "sigma(28)"}), flush=True)
    sys.exit(1)
if [n for n in range(2, 30) if is_prime(n)] != [2,3,5,7,11,13,17,19,23,29]:
    print(json.dumps({"event": "shakedown_failed", "detail": "primality"}), flush=True)
    sys.exit(1)
print(json.dumps({"event": "shakedown", "result": "passed",
                  "checked": "sigma(1..10), sigma(28)=56, primes below 30"}), flush=True)

# --- the search -----------------------------------------------------------------
checkpoint = os.environ["SEARCH_CHECKPOINT"]
state = os.environ["SEARCH_STATE"]
MAX_STEPS = int(os.environ.get("MAX_STEPS", "200"))
MAX_VALORE = int(os.environ.get("MAX_VALORE", str(10**14)))
UP_TO = int(os.environ.get("UP_TO", "200000"))

n0 = 2
found = []
examined = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    n0 = max(2, d.get("position", 2))
    found = d.get("found", [])
    examined = d.get("examined", 0)

stopped = False
def stop(s, f):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

def salva(n):
    tmp = state + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"position": n, "examined": examined, "found": found}, f)
    os.replace(tmp, state)

t0 = time.time(); last = t0
n = n0
while n <= UP_TO and not stopped:
    m = n
    seen = set()
    result = None
    for step in range(MAX_STEPS):
        if is_prime(m):
            result = ("first", step, m)
            break
        if m in seen:
            result = ("cycle", step, m)
            break
        seen.add(m)
        m = sigma(m) - 1
        if m > MAX_VALUE:
            result = ("too_large", step, m)
            break
        if m <= 1:
            result = ("degenerate", step, m)
            break
    if result is None:
        result = ("no_prime_within_the_steps", MAX_STEPS, m)
    if result[0] != "first":
        found.append({"n": n, "result": result[0], "steps": result[1],
                        "value": result[2]})
        print(json.dumps({"event": "found", "detail": found[-1]}), flush=True)
    examined += 1
    n += 1
    now = time.time()
    if now - last > 30:
        salva(n)
        print(json.dumps({"event": "progress", "position": n,
                          "examined": examined, "seconds": round(now - t0)}), flush=True)
        last = now

salva(n)
print(json.dumps({"event": "end", "position": n, "examined": examined,
                  "found": len(found), "seconds": round(time.time() - t0)}), flush=True)
'''


# ---------------------------------------------------------------------------
# 3. Erdos 396: a descending factorial dividing the central binomial coefficient
#    centrale
# ---------------------------------------------------------------------------
# PROBLEM: Erdos396.erdos_396
#   True ↔ ∀ k, ∃ n, descFactorial n (k+1) ∣ centralBinom n
#
# This does NOT look for a counterexample outright: the statement is a "for every k
# there exists n", so refuting it would need a k for which NO n works, and computation
# cannot establish that. What computation can do is useful all the same: for each k,
# find the least n that works. If for some k the least n explodes, that is evidence; if
# one is always found early, that is experimental confirmation.
BINOMIAL = r'''
import json, os, signal, sys, time
from math import comb

def desc_factorial(n, k):
    """n * (n-1) * ... * (n-k+1)"""
    r = 1
    for i in range(k):
        r *= (n - i)
    return r

def central_binom(n):
    return comb(2 * n, n)

# --- SELF-TEST on known values -------------------------------------------------
if [central_binom(n) for n in range(6)] != [1, 2, 6, 20, 70, 252]:
    print(json.dumps({"event": "shakedown_failed", "detail": "centralBinom"}), flush=True)
    sys.exit(1)
if desc_factorial(7, 3) != 7 * 6 * 5:
    print(json.dumps({"event": "shakedown_failed", "detail": "descFactorial"}), flush=True)
    sys.exit(1)
if desc_factorial(5, 0) != 1:
    print(json.dumps({"event": "shakedown_failed", "detail": "descFactorial(n,0)"}), flush=True)
    sys.exit(1)
print(json.dumps({"event": "shakedown", "result": "passed",
                  "checked": "centralBinom(0..5) = 1,2,6,20,70,252 and descFactorial"}),
      flush=True)

checkpoint = os.environ["SEARCH_CHECKPOINT"]
state = os.environ["SEARCH_STATE"]
K_MAX = int(os.environ.get("K_MAX", "60"))
N_MAX = int(os.environ.get("N_MAX", "20000"))

k0 = 0
found = []
minima = []
examined = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    k0 = d.get("position", 0)
    found = d.get("found", [])
    minima = d.get("minima", [])
    examined = d.get("examined", 0)

stopped = False
def stop(s, f):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

def salva(k):
    tmp = state + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"position": k, "examined": examined, "found": found,
                   "minima": minima}, f)
    os.replace(tmp, state)

t0 = time.time(); last = t0
for k in range(k0, K_MAX + 1):
    if stopped:
        break
    foundn = None
    for n in range(k + 1, N_MAX):
        if central_binom(n) % desc_factorial(n, k + 1) == 0:
            foundn = n
            break
    examined += 1
    entry = {"k": k, "n_minimo": foundn}
    minima.append(entry)
    if foundn is None:
        # This is NOT a counterexample: the form "for every k there exists n" cannot
        # be refuted by computation. It is evidence: up to N_MAX there is no such n.
        found.append({"k": k, "nessun_n_fino_a": N_MAX,
                        "warning": "evidence, not a counterexample"})
    print(json.dumps({"event": "progress", "detail": entry,
                      "position": k + 1, "examined": examined}), flush=True)
    now = time.time()
    if now - last > 30:
        salva(k + 1); last = now

salva(k + 1 if not stopped else k)
print(json.dumps({"event": "end", "position": k, "examined": examined,
                  "seconds": round(time.time() - t0)}), flush=True)
'''



MURTHY = r'''
import json, os, signal, sys, time

from sympy import isprime

def esiste_k(n):
    """The least k with k(n-k)-1 prime, or None if there is none."""
    for k in range(1, n // 2 + 1):
        if isprime(k * (n - k) - 1):
            return k
    return None

# --- SELF-TEST on known values ------------------------------------------------
# The archive's test theorems (OEIS/109909.lean) fix:
#   a(1)=0, a(2)=0, a(3)=0, a(4)=2  (number of distinct primes k(n-k)-1)
# Only the part the search needs is checked here: k exists for n=4..8 and does NOT
# exist for n=1,2,3.
expected_without = [1, 2, 3]
expected_with = [4, 5, 6, 7, 8]
for n in attesi_senza:
    if esiste_k(n) is not None:
        print(json.dumps({"event": "shakedown_failed", "n": n,
                          "detail": "found k where the archive says a(n)=0"}), flush=True)
        sys.exit(1)
for n in attesi_con:
    if esiste_k(n) is None:
        print(json.dumps({"event": "shakedown_failed", "n": n,
                          "detail": "no k where the archive says a(n)>0"}), flush=True)
        sys.exit(1)
print(json.dumps({"event": "shakedown", "result": "passed",
                  "checked": "n=1,2,3 with no k; n=4..8 with k, as the archive's "
                                 "test theorems say"}), flush=True)

# --- the search ----------------------------------------------------------------
checkpoint = os.environ["SEARCH_CHECKPOINT"]
state = os.environ["SEARCH_STATE"]
DA = int(os.environ.get("FROM", "4"))
UP_TO = int(os.environ.get("UP_TO", "1000000000"))

start = DA
found = []
examined = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    start = d.get("position", DA)
    found = d.get("found", [])
    examined = d.get("examined", 0)

stopped = False
def stop(s, f):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

def salva(n):
    tmp = state + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"position": n, "examined": examined, "found": found,
                   "ultimo_n": n - 1}, fh)
    os.replace(tmp, state)

print(json.dumps({"event": "start", "da": start, "fino_a": UP_TO}), flush=True)
t0 = time.time()
last_warning = t0
n = start
while n < UP_TO and not stopped:
    if esiste_k(n) is None:
        found.append({"n": n, "note": "no k with k(n-k)-1 prime: COUNTEREXAMPLE"})
        print(json.dumps({"event": "found", "detail": found[-1]}), flush=True)
    examined += 1
    n += 1
    now = time.time()
    if now - last_warning > 30:
        salva(n)
        print(json.dumps({"event": "progress", "position": n,
                          "examined": examined, "current_n": n,
                          "seconds": round(now - t0)}), flush=True)
        last_warning = now

salva(n)
print(json.dumps({"event": "end", "position": n, "examined": examined,
                  "found": len(found), "seconds": round(time.time() - t0)}),
      flush=True)
'''

SEARCHES = {
    "euclid_squarefree": {
        "problem": "EuclidNumbers.euclid_numbers_are_square_free",
        "program": EUCLID,
        # MEASURED: 17984 primes (all those below 200000) examined in 17 seconds,
        # no findings. The cost grows as the square of the limit, so 2 million is
        # about a hundred times as much: half an hour.
        "variables": {"LIMIT_P": 3000000},
        "description": "looks for a prime p with p² dividing a Euclid number",
        "known_state": "open; no published systematic search found",
        "conclusive": "yes: a single p found refutes the conjecture",
        # What ends up in the program's `found` list: real counterexamples, or
        # computed values that have to be interpreted?
        "nature_of_findings": "counterexamples",
        # How a result with no findings reads, in mathematical terms. It is
        # formatted with the result's fields, the search's variables and
        # l'last event del log.
        "result_in_words":
            "no prime p up to {current_prime} has p^2 dividing a Euclid number. "
            "{examined} primes were examined, and for each of them ALL primorials "
            "with factors smaller than p: for those p the check is complete, not "
            "partial.",
    },
    "erdos409_sigma": {
        "problem": "Erdos409.erdos_409.variants.sigma_prime_termination",
        "program": SIGMA,
        "variables": {"UP_TO": 200000, "MAX_STEPS": 200},
        "description": "iterates n -> sigma(n)-1 and looks for orbits that never hit a prime",
        "known_state": "open",
        "conclusive": "no: it finds SUSPECTS, not counterexamples. An orbit that does "
                      "not reach a prime in 200 steps has to be examined by hand",
        "nature_of_findings": "suspects",
        "result_in_words":
            "no n up to {UP_TO} generates an orbit of n -> sigma(n)-1 that avoids the "
            "primes for {MAX_STEPS} steps.",
    },
    "murthy_kn_k": {
        "problem": "OeisA109909.conjecture",
        "program": MURTHY,
        # MEASURED: 157,000 n/s at n around 10^6 on one core (sympy.isprime, and the
        # first k nearly always works). A billion is ~1.8 hours.
        "variables": {"FROM": 4, "UP_TO": 1000000000},
        "description": "for each n > 3 looks for k with k(n-k)-1 prime; an n without "
                       "such k refutes A. Murthy's conjecture (2005)",
        "known_state": "open; cited in Zhi-Wei Sun's collection "
                       "(arXiv:1211.1588) and in Niu-Zhang 2024. The published "
                       "frontier is not precisely known: this search at least "
                       "establishes ours",
        "conclusive": "yes: a single n without k refutes the conjecture, and for a "
                      "moderate n the refutation can be checked in Lean too",
        "nature_of_findings": "counterexamples",
        "result_in_words":
            "every n from 4 to {current_n} has at least one k with k(n-k)-1 prime: "
            "Murthy's conjecture holds that far. {examined} values of n "
            "were examined.",
    },
    "erdos396_binomial": {
        "problem": "Erdos396.erdos_396",
        "program": BINOMIAL,
        "variables": {"K_MAX": 60, "N_MAX": 20000},
        "description": "for each k, the least n with descFactorial(n,k+1) | centralBinom(n)",
        "known_state": "open",
        "conclusive": "no: the form is 'for every k there exists n', which computation "
                      "cannot refute. It serves to gather evidence",
        "nature_of_findings": "results computed",
        "result_in_words":
            "for each k up to {K_MAX} the least n up to {N_MAX} with "
            "descFactorial(n, k+1) dividing centralBinom(n) was sought.",
    },
}
