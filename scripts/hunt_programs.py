"""
I programmi di ricerca, one per problem.

Ogni program rispetta il contratto di verifier/search.py: legge il
checkpoint, salva i progressi, gestisce SIGTERM, non usa la rete.

Ogni program ha in cima un block COLLAUDO che ricalcola valori NOTI e si
ferma se non combaciano. Una ricerca che parte da un computation sbagliato produce
un ritrovamento falso, che e' peggio di nessun ritrovamento.
"""

# ---------------------------------------------------------------------------
# 1. Numeri di Euclide senza fattori quadrati
# ---------------------------------------------------------------------------
# PROBLEM: EuclidNumbers.euclid_numbers_are_square_free
#   True ↔ ∀ n, Squarefree (Euclid n)      con Euclid n = p_n# + 1
#
# STATO NOTO (cercato sul web il 2026-09-10): e' aperto se ogni number di
# Euclide sia privo di fattori quadrati. Non risulta pubblicata one_ ricerca
# sistematica di controesempi.
#
# COME SI CERCA: se p² divide p_n# + 1, allora p non divide p_n#, quindi p e'
# maggiore di p_n. Per ogni prime_ p si compute il primoriale module p²,
# moltiplicando un prime_ q < p alla volta, e si guarda se in qualche momento
# vale −1 module p². Costo: circa π(p) operazioni per ogni p, cioe' P²/(2 ln²P)
# in total. Per P = 10^6 sono un paio di miliardi di moltiplicazioni: hours, non
# giorni.
EUCLID = r'''
import json, os, signal, sys, time

def cribro(n):
    """Primi fino a n, con il crivello di Eratostene."""
    s = bytearray([1]) * (n + 1)
    s[0:2] = b"\x00\x00"
    i = 2
    while i * i <= n:
        if s[i]:
            s[i*i::i] = bytearray(len(s[i*i::i]))
        i += 1
    return [i for i in range(n + 1) if s[i]]

# --- COLLAUDO su valori noti -------------------------------------------------
# I primes numbers di Euclide sono 3, 7, 31, 211, 2311, 30031, 510511.
expected = [3, 7, 31, 211, 2311, 30031, 510511]
pr = cribro(100)
acc, computed = 1, []
for q in pr[:7]:
    acc *= q
    computed.append(acc + 1)
if computed != expected:
    print(json.dumps({"event": "collaudo_fallito",
                      "expected_one": expected, "calcolato": computed}), flush=True)
    sys.exit(1)
# 30031 = 59 * 509: il sesto number di Euclide NON e' prime_ (ma e' senza quadrati)
if 30031 % 59 != 0:
    print(json.dumps({"event": "collaudo_fallito", "detail": "30031 = 59*509"}), flush=True)
    sys.exit(1)
print(json.dumps({"event": "shakedown", "result": "passed_one",
                  "controllati": "primes 7 numbers di Euclide e la fattorizzazione di 30031"}),
      flush=True)

# --- ricerca -----------------------------------------------------------------
checkpoint = os.environ["SEARCH_CHECKPOINT"]
state = os.environ["SEARCH_STATE"]
LIMIT = int(os.environ.get("LIMITE_P", "200000"))

index_start = 0
found = []
examined = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    index_start = d.get("position", 0)
    found = d.get("found", [])
    examined = d.get("examined", 0)

primes = cribro(LIMIT)
print(json.dumps({"event": "start_", "primi_disponibili": len(primes),
                  "limit": LIMIT, "riparto_da_indice": index_start}), flush=True)

stopped = False
def stop_(s, f):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop_)
signal.signal(signal.SIGINT, stop_)

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
    # il primoriale module p^2, un prime_ q < p alla volta
    for j in range(i):          # all_of i primes q < p
        acc = (acc * primes[j]) % p2
        if acc == p2 - 1:       # acc ≡ -1 (mod p^2), cioe' p^2 | p_n# + 1
            found.append({"p": p, "indice_primoriale": j + 1,
                            "ultimo_primo_del_primoriale": primes[j]})
            print(json.dumps({"event": "found",
                              "detail": found[-1]}), flush=True)
    examined += 1
    now_ = time.time()
    if now_ - last_warning > 30:
        salva(i + 1)
        print(json.dumps({"event": "progress", "position": i + 1,
                          "examined": examined, "primo_corrente": p,
                          "seconds": round(now_ - t0)}), flush=True)
        last_warning = now_

salva(min(i + 1, len(primes)))
print(json.dumps({"event": "end", "position": min(i + 1, len(primes)),
                  "examined": examined, "found": len(found),
                  "seconds": round(time.time() - t0)}), flush=True)
'''


# ---------------------------------------------------------------------------
# 2. Erdos 409: l'iteration di sigma meno one raggiunge sempre un prime_?
# ---------------------------------------------------------------------------
# PROBLEM: Erdos409.erdos_409.variants.sigma_prime_termination
#   True ↔ ∀ n > 1, ∃ i, Prime ((fun x => σ₁(x) - 1)^[i] n)
#
# COME SI CERCA: per ogni n si itera m ↦ σ(m) − 1 finche' non si incontra un
# prime_. Un counterexample e' un n la cui orbit non incontra mai un prime_:
# o enters in un ciclo, o cresce senza limit. Si fix_ un cap di steps e di
# grandezza; chi lo supera viene segnalato come SOSPETTO, non come
# counterexample — distinzione importante, perche' "non l'ho found in mille
# steps" non e' "non esiste".
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
    """Somma dei divisori."""
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

# --- COLLAUDO su valori noti -------------------------------------------------
# sigma: 1,3,4,7,6,12,8,15,13,18 per n = 1..10
expected = [1, 3, 4, 7, 6, 12, 8, 15, 13, 18]
computed = [sigma(n) for n in range(1, 11)]
if computed != expected:
    print(json.dumps({"event": "collaudo_fallito", "expected_one": expected,
                      "calcolato": computed}), flush=True)
    sys.exit(1)
# sigma(28) = 56 perche' 28 e' perfetto
if sigma(28) != 56:
    print(json.dumps({"event": "collaudo_fallito", "detail": "sigma(28)"}), flush=True)
    sys.exit(1)
if [n for n in range(2, 30) if is_prime(n)] != [2,3,5,7,11,13,17,19,23,29]:
    print(json.dumps({"event": "collaudo_fallito", "detail": "primalita'"}), flush=True)
    sys.exit(1)
print(json.dumps({"event": "shakedown", "result": "passed_one",
                  "controllati": "sigma(1..10), sigma(28)=56, primes below 30"}), flush=True)

# --- ricerca -----------------------------------------------------------------
checkpoint = os.environ["SEARCH_CHECKPOINT"]
state = os.environ["SEARCH_STATE"]
MAX_STEPS = int(os.environ.get("MAX_STEPS", "200"))
MAX_VALORE = int(os.environ.get("MAX_VALORE", str(10**14)))
FINO_A = int(os.environ.get("FINO_A", "200000"))

n0 = 2
found = []
examined = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    n0 = max(2, d.get("position", 2))
    found = d.get("found", [])
    examined = d.get("examined", 0)

stopped = False
def stop_(s, f):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop_)
signal.signal(signal.SIGINT, stop_)

def salva(n):
    tmp = state + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"position": n, "examined": examined, "found": found}, f)
    os.replace(tmp, state)

t0 = time.time(); last_ = t0
n = n0
while n <= FINO_A and not stopped:
    m = n
    seen = set()
    result = None
    for step in range(MAX_STEPS):
        if is_prime(m):
            result = ("prime_", step, m)
            break
        if m in seen:
            result = ("ciclo", step, m)
            break
        seen.add(m)
        m = sigma(m) - 1
        if m > MAX_VALORE:
            result = ("troppo_grande", step, m)
            break
        if m <= 1:
            result = ("degenere", step, m)
            break
    if result is None:
        result = ("nessun_primo_entro_i_passi", MAX_STEPS, m)
    if result[0] != "prime_":
        found.append({"n": n, "result": result[0], "steps": result[1],
                        "value_": result[2]})
        print(json.dumps({"event": "found", "detail": found[-1]}), flush=True)
    examined += 1
    n += 1
    now_ = time.time()
    if now_ - last_ > 30:
        salva(n)
        print(json.dumps({"event": "progress", "position": n,
                          "examined": examined, "seconds": round(now_ - t0)}), flush=True)
        last_ = now_

salva(n)
print(json.dumps({"event": "end", "position": n, "examined": examined,
                  "found": len(found), "seconds": round(time.time() - t0)}), flush=True)
'''


# ---------------------------------------------------------------------------
# 3. Erdos 396: fattoriale discendente che divide il coefficiente binomiale
#    centrale
# ---------------------------------------------------------------------------
# PROBLEM: Erdos396.erdos_396
#   True ↔ ∀ k, ∃ n, descFactorial n (k+1) ∣ centralBinom n
#
# Qui NON si search_for un counterexample a colpo sicuro: l'statement e' un "per ogni
# k esiste n", quindi per confutarlo servirebbe un k per cui NESSUN n funziona,
# e questo un computation non lo puo' stabilire. Quello che il computation puo' fare e'
# utile lo stesso: per ogni k, trovare il piu' piccolo n che funziona. Se per
# qualche k il piu' piccolo n esplode, e' un indizio; se si trova sempre presto,
# e' one_ conferma sperimentale.
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

# --- COLLAUDO su valori noti -------------------------------------------------
if [central_binom(n) for n in range(6)] != [1, 2, 6, 20, 70, 252]:
    print(json.dumps({"event": "collaudo_fallito", "detail": "centralBinom"}), flush=True)
    sys.exit(1)
if desc_factorial(7, 3) != 7 * 6 * 5:
    print(json.dumps({"event": "collaudo_fallito", "detail": "descFactorial"}), flush=True)
    sys.exit(1)
if desc_factorial(5, 0) != 1:
    print(json.dumps({"event": "collaudo_fallito", "detail": "descFactorial(n,0)"}), flush=True)
    sys.exit(1)
print(json.dumps({"event": "shakedown", "result": "passed_one",
                  "controllati": "centralBinom(0..5) = 1,2,6,20,70,252 e descFactorial"}),
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
def stop_(s, f):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop_)
signal.signal(signal.SIGINT, stop_)

def salva(k):
    tmp = state + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"position": k, "examined": examined, "found": found,
                   "minima": minima}, f)
    os.replace(tmp, state)

t0 = time.time(); last_ = t0
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
        # NON e' un counterexample: la forma "per ogni k esiste n" non si
        # confuta con un computation. E' un indizio: fino a N_MAX non c'e' nessun n.
        found.append({"k": k, "nessun_n_fino_a": N_MAX,
                        "avvertenza": "indizio, non counterexample"})
    print(json.dumps({"event": "progress", "detail": entry,
                      "position": k + 1, "examined": examined}), flush=True)
    now_ = time.time()
    if now_ - last_ > 30:
        salva(k + 1); last_ = now_

salva(k + 1 if not stopped else k)
print(json.dumps({"event": "end", "position": k, "examined": examined,
                  "seconds": round(time.time() - t0)}), flush=True)
'''



MURTHY = r'''
import json, os, signal, sys, time

from sympy import isprime

def esiste_k(n):
    """Il piu' piccolo k con k(n-k)-1 prime_, o None se non esiste."""
    for k in range(1, n // 2 + 1):
        if isprime(k * (n - k) - 1):
            return k
    return None

# --- COLLAUDO su valori noti ------------------------------------------------
# I theorems di trial dell'archive (OEIS/109909.lean) fissano:
#   a(1)=0, a(2)=0, a(3)=0, a(4)=2  (number di primes distinti k(n-k)-1)
# Qui basta la parte che serve alla ricerca: esiste k per n=4..8 e NON esiste
# per n=1,2,3.
attesi_senza = [1, 2, 3]
attesi_con = [4, 5, 6, 7, 8]
for n in attesi_senza:
    if esiste_k(n) is not None:
        print(json.dumps({"event": "collaudo_fallito", "n": n,
                          "detail": "found k dove l'archive dice a(n)=0"}), flush=True)
        sys.exit(1)
for n in attesi_con:
    if esiste_k(n) is None:
        print(json.dumps({"event": "collaudo_fallito", "n": n,
                          "detail": "nessun k dove l'archive dice a(n)>0"}), flush=True)
        sys.exit(1)
print(json.dumps({"event": "shakedown", "result": "passed_one",
                  "controllati": "n=1,2,3 senza k; n=4..8 con k, come i theorems "
                                 "di trial dell'archive"}), flush=True)

# --- ricerca ----------------------------------------------------------------
checkpoint = os.environ["SEARCH_CHECKPOINT"]
state = os.environ["SEARCH_STATE"]
DA = int(os.environ.get("DA", "4"))
FINO_A = int(os.environ.get("FINO_A", "1000000000"))

start = DA
found = []
examined = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    start = d.get("position", DA)
    found = d.get("found", [])
    examined = d.get("examined", 0)

stopped = False
def stop_(s, f):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop_)
signal.signal(signal.SIGINT, stop_)

def salva(n):
    tmp = state + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"position": n, "examined": examined, "found": found,
                   "ultimo_n": n - 1}, fh)
    os.replace(tmp, state)

print(json.dumps({"event": "start_", "da": start, "fino_a": FINO_A}), flush=True)
t0 = time.time()
last_warning = t0
n = start
while n < FINO_A and not stopped:
    if esiste_k(n) is None:
        found.append({"n": n, "note": "nessun k con k(n-k)-1 prime_: CONTROESEMPIO"})
        print(json.dumps({"event": "found", "detail": found[-1]}), flush=True)
    examined += 1
    n += 1
    now_ = time.time()
    if now_ - last_warning > 30:
        salva(n)
        print(json.dumps({"event": "progress", "position": n,
                          "examined": examined, "n_corrente": n,
                          "seconds": round(now_ - t0)}), flush=True)
        last_warning = now_

salva(n)
print(json.dumps({"event": "end", "position": n, "examined": examined,
                  "found": len(found), "seconds": round(time.time() - t0)}),
      flush=True)
'''

SEARCHES = {
    "euclide_squarefree": {
        "problem": "EuclidNumbers.euclid_numbers_are_square_free",
        "program": EUCLID,
        # MISURATO: 17984 primes (all_of below 200000) examined in 17 seconds,
        # nessun ritrovamento. Il cost cresce come il quadrato del limit,
        # quindi 2 milioni sono circa cento volte tanto: one_ mezz'now_.
        "variables": {"LIMITE_P": 3000000},
        "descrizione": "search_for un prime_ p con p² che divide un number di Euclide",
        "stato_noto": "aperto; non risulta one_ ricerca sistematica pubblicata",
        "conclusivo": "si: un only_ p found confuta la congettura",
        # Che cosa finisce nella list_ `found` del program: real_ones
        # controesempi, oppure valori computed che vanno interpretati?
        "natura_trovati": "controesempi",
        # Come si legge un result senza ritrovamenti, in termini matematici.
        # Si formatta con i fields dell'result, le variables della ricerca e
        # l'last_ event del log_.
        "esito_in_parole":
            "nessun prime_ p fino a {primo_corrente} ha p^2 che divide un number "
            "di Euclide. Sono stati examined {examined} primes, e per ognuno "
            "TUTTI i primoriali con fattori minori di p: per quei p il "
            "controllo e' full_, non partial.",
    },
    "erdos409_sigma": {
        "problem": "Erdos409.erdos_409.variants.sigma_prime_termination",
        "program": SIGMA,
        "variables": {"FINO_A": 200000, "MAX_STEPS": 200},
        "descrizione": "itera n -> sigma(n)-1 e search_for orbits che non toccano mai un prime_",
        "stato_noto": "aperto",
        "conclusivo": "no: trova SOSPETTI, non controesempi. Un'orbit che non "
                      "raggiunge un prime_ in 200 steps va esaminata a mano",
        "natura_trovati": "sospetti",
        "esito_in_parole":
            "nessun n fino a {FINO_A} generate un'orbit di n -> sigma(n)-1 che "
            "eviti i numbers primes per {MAX_STEPS} steps.",
    },
    "murthy_kn_k": {
        "problem": "OeisA109909.conjecture",
        "program": MURTHY,
        # MISURATO: 157 000 n/s a n circa 10^6 su un core (sympy.isprime, e il
        # prime_ k funziona quasi sempre). Un miliardo sono ~1,8 hours.
        "variables": {"DA": 4, "FINO_A": 1000000000},
        "descrizione": "per ogni n > 3 search_for k con k(n-k)-1 prime_; un n senza "
                       "k confuta la congettura di A. Murthy (2005)",
        "stato_noto": "aperta; citata nella raccolta di Zhi-Wei Sun "
                      "(arXiv:1211.1588) e in Niu-Zhang 2024. La frontier "
                      "pubblicata non e' note con precisione: questa ricerca "
                      "stabilisce almeno la nostra",
        "conclusivo": "si: un only_ n senza k confuta la congettura, e per un n "
                      "moderato la confutazione si check also_ in Lean",
        "natura_trovati": "controesempi",
        "esito_in_parole":
            "ogni n da 4 a {n_corrente} ha almeno un k con k(n-k)-1 prime_: "
            "la congettura di Murthy regge fino a la'. Esaminati {examined} "
            "valori di n.",
    },
    "erdos396_binomiale": {
        "problem": "Erdos396.erdos_396",
        "program": BINOMIAL,
        "variables": {"K_MAX": 60, "N_MAX": 20000},
        "descrizione": "per ogni k, il piu' piccolo n con descFactorial(n,k+1) | centralBinom(n)",
        "stato_noto": "aperto",
        "conclusivo": "no: la forma e' 'per ogni k esiste n', che un computation non "
                      "puo' confutare. Serve a raccogliere indizi",
        "natura_trovati": "results computed",
        "esito_in_parole":
            "per ogni k fino a {K_MAX} si e' cercato il minimum n fino a {N_MAX} "
            "con descFactorial(n, k+1) che divide centralBinom(n).",
    },
}
