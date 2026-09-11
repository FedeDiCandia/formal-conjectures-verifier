"""
I programmi di ricerca, uno per problema.

Ogni programma rispetta il contratto di verifier/ricerca.py: legge il
checkpoint, salva i progressi, gestisce SIGTERM, non usa la rete.

Ogni programma ha in cima un blocco COLLAUDO che ricalcola valori NOTI e si
ferma se non combaciano. Una ricerca che parte da un calcolo sbagliato produce
un ritrovamento falso, che e' peggio di nessun ritrovamento.
"""

# ---------------------------------------------------------------------------
# 1. Numeri di Euclide senza fattori quadrati
# ---------------------------------------------------------------------------
# PROBLEMA: EuclidNumbers.euclid_numbers_are_square_free
#   True ↔ ∀ n, Squarefree (Euclid n)      con Euclid n = p_n# + 1
#
# STATO NOTO (cercato sul web il 2026-09-10): e' aperto se ogni numero di
# Euclide sia privo di fattori quadrati. Non risulta pubblicata una ricerca
# sistematica di controesempi.
#
# COME SI CERCA: se p² divide p_n# + 1, allora p non divide p_n#, quindi p e'
# maggiore di p_n. Per ogni primo p si calcola il primoriale modulo p²,
# moltiplicando un primo q < p alla volta, e si guarda se in qualche momento
# vale −1 modulo p². Costo: circa π(p) operazioni per ogni p, cioe' P²/(2 ln²P)
# in totale. Per P = 10^6 sono un paio di miliardi di moltiplicazioni: ore, non
# giorni.
EUCLIDE = r'''
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
# I primi numeri di Euclide sono 3, 7, 31, 211, 2311, 30031, 510511.
attesi = [3, 7, 31, 211, 2311, 30031, 510511]
pr = cribro(100)
acc, calcolati = 1, []
for q in pr[:7]:
    acc *= q
    calcolati.append(acc + 1)
if calcolati != attesi:
    print(json.dumps({"evento": "collaudo_fallito",
                      "atteso": attesi, "calcolato": calcolati}), flush=True)
    sys.exit(1)
# 30031 = 59 * 509: il sesto numero di Euclide NON e' primo (ma e' senza quadrati)
if 30031 % 59 != 0:
    print(json.dumps({"evento": "collaudo_fallito", "dettaglio": "30031 = 59*509"}), flush=True)
    sys.exit(1)
print(json.dumps({"evento": "collaudo", "esito": "superato",
                  "controllati": "primi 7 numeri di Euclide e la fattorizzazione di 30031"}),
      flush=True)

# --- ricerca -----------------------------------------------------------------
checkpoint = os.environ["RICERCA_CHECKPOINT"]
stato = os.environ["RICERCA_STATO"]
LIMITE = int(os.environ.get("LIMITE_P", "200000"))

inizio_indice = 0
trovati = []
esaminati = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    inizio_indice = d.get("posizione", 0)
    trovati = d.get("trovati", [])
    esaminati = d.get("esaminati", 0)

primi = cribro(LIMITE)
print(json.dumps({"evento": "avvio", "primi_disponibili": len(primi),
                  "limite": LIMITE, "riparto_da_indice": inizio_indice}), flush=True)

fermati = False
def arresto(s, f):
    global fermati
    fermati = True
signal.signal(signal.SIGTERM, arresto)
signal.signal(signal.SIGINT, arresto)

def salva(i):
    tmp = stato + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"posizione": i, "esaminati": esaminati, "trovati": trovati,
                   "ultimo_primo": primi[i - 1] if i else None}, f)
    os.replace(tmp, stato)

t0 = time.time()
ultimo_avviso = t0
for i in range(inizio_indice, len(primi)):
    if fermati:
        break
    p = primi[i]
    p2 = p * p
    acc = 1
    # il primoriale modulo p^2, un primo q < p alla volta
    for j in range(i):          # tutti i primi q < p
        acc = (acc * primi[j]) % p2
        if acc == p2 - 1:       # acc ≡ -1 (mod p^2), cioe' p^2 | p_n# + 1
            trovati.append({"p": p, "indice_primoriale": j + 1,
                            "ultimo_primo_del_primoriale": primi[j]})
            print(json.dumps({"evento": "trovato",
                              "dettaglio": trovati[-1]}), flush=True)
    esaminati += 1
    ora = time.time()
    if ora - ultimo_avviso > 30:
        salva(i + 1)
        print(json.dumps({"evento": "progresso", "posizione": i + 1,
                          "esaminati": esaminati, "primo_corrente": p,
                          "secondi": round(ora - t0)}), flush=True)
        ultimo_avviso = ora

salva(min(i + 1, len(primi)))
print(json.dumps({"evento": "fine", "posizione": min(i + 1, len(primi)),
                  "esaminati": esaminati, "trovati": len(trovati),
                  "secondi": round(time.time() - t0)}), flush=True)
'''


# ---------------------------------------------------------------------------
# 2. Erdos 409: l'iterazione di sigma meno uno raggiunge sempre un primo?
# ---------------------------------------------------------------------------
# PROBLEMA: Erdos409.erdos_409.variants.sigma_prime_termination
#   True ↔ ∀ n > 1, ∃ i, Prime ((fun x => σ₁(x) - 1)^[i] n)
#
# COME SI CERCA: per ogni n si itera m ↦ σ(m) − 1 finche' non si incontra un
# primo. Un controesempio e' un n la cui orbita non incontra mai un primo:
# o entra in un ciclo, o cresce senza limite. Si fissa un tetto di passi e di
# grandezza; chi lo supera viene segnalato come SOSPETTO, non come
# controesempio — distinzione importante, perche' "non l'ho trovato in mille
# passi" non e' "non esiste".
SIGMA = r'''
import json, os, signal, sys, time

def fattorizza(n):
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
    for p, e in fattorizza(n).items():
        s *= (p ** (e + 1) - 1) // (p - 1)
    return s

def e_primo(n):
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
attesi = [1, 3, 4, 7, 6, 12, 8, 15, 13, 18]
calcolati = [sigma(n) for n in range(1, 11)]
if calcolati != attesi:
    print(json.dumps({"evento": "collaudo_fallito", "atteso": attesi,
                      "calcolato": calcolati}), flush=True)
    sys.exit(1)
# sigma(28) = 56 perche' 28 e' perfetto
if sigma(28) != 56:
    print(json.dumps({"evento": "collaudo_fallito", "dettaglio": "sigma(28)"}), flush=True)
    sys.exit(1)
if [n for n in range(2, 30) if e_primo(n)] != [2,3,5,7,11,13,17,19,23,29]:
    print(json.dumps({"evento": "collaudo_fallito", "dettaglio": "primalita'"}), flush=True)
    sys.exit(1)
print(json.dumps({"evento": "collaudo", "esito": "superato",
                  "controllati": "sigma(1..10), sigma(28)=56, primi sotto 30"}), flush=True)

# --- ricerca -----------------------------------------------------------------
checkpoint = os.environ["RICERCA_CHECKPOINT"]
stato = os.environ["RICERCA_STATO"]
MAX_PASSI = int(os.environ.get("MAX_PASSI", "200"))
MAX_VALORE = int(os.environ.get("MAX_VALORE", str(10**14)))
FINO_A = int(os.environ.get("FINO_A", "200000"))

n0 = 2
trovati = []
esaminati = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    n0 = max(2, d.get("posizione", 2))
    trovati = d.get("trovati", [])
    esaminati = d.get("esaminati", 0)

fermati = False
def arresto(s, f):
    global fermati
    fermati = True
signal.signal(signal.SIGTERM, arresto)
signal.signal(signal.SIGINT, arresto)

def salva(n):
    tmp = stato + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"posizione": n, "esaminati": esaminati, "trovati": trovati}, f)
    os.replace(tmp, stato)

t0 = time.time(); ultimo = t0
n = n0
while n <= FINO_A and not fermati:
    m = n
    visti = set()
    esito = None
    for passo in range(MAX_PASSI):
        if e_primo(m):
            esito = ("primo", passo, m)
            break
        if m in visti:
            esito = ("ciclo", passo, m)
            break
        visti.add(m)
        m = sigma(m) - 1
        if m > MAX_VALORE:
            esito = ("troppo_grande", passo, m)
            break
        if m <= 1:
            esito = ("degenere", passo, m)
            break
    if esito is None:
        esito = ("nessun_primo_entro_i_passi", MAX_PASSI, m)
    if esito[0] != "primo":
        trovati.append({"n": n, "esito": esito[0], "passi": esito[1],
                        "valore": esito[2]})
        print(json.dumps({"evento": "trovato", "dettaglio": trovati[-1]}), flush=True)
    esaminati += 1
    n += 1
    ora = time.time()
    if ora - ultimo > 30:
        salva(n)
        print(json.dumps({"evento": "progresso", "posizione": n,
                          "esaminati": esaminati, "secondi": round(ora - t0)}), flush=True)
        ultimo = ora

salva(n)
print(json.dumps({"evento": "fine", "posizione": n, "esaminati": esaminati,
                  "trovati": len(trovati), "secondi": round(time.time() - t0)}), flush=True)
'''


# ---------------------------------------------------------------------------
# 3. Erdos 396: fattoriale discendente che divide il coefficiente binomiale
#    centrale
# ---------------------------------------------------------------------------
# PROBLEMA: Erdos396.erdos_396
#   True ↔ ∀ k, ∃ n, descFactorial n (k+1) ∣ centralBinom n
#
# Qui NON si cerca un controesempio a colpo sicuro: l'enunciato e' un "per ogni
# k esiste n", quindi per confutarlo servirebbe un k per cui NESSUN n funziona,
# e questo un calcolo non lo puo' stabilire. Quello che il calcolo puo' fare e'
# utile lo stesso: per ogni k, trovare il piu' piccolo n che funziona. Se per
# qualche k il piu' piccolo n esplode, e' un indizio; se si trova sempre presto,
# e' una conferma sperimentale.
BINOMIALE = r'''
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
    print(json.dumps({"evento": "collaudo_fallito", "dettaglio": "centralBinom"}), flush=True)
    sys.exit(1)
if desc_factorial(7, 3) != 7 * 6 * 5:
    print(json.dumps({"evento": "collaudo_fallito", "dettaglio": "descFactorial"}), flush=True)
    sys.exit(1)
if desc_factorial(5, 0) != 1:
    print(json.dumps({"evento": "collaudo_fallito", "dettaglio": "descFactorial(n,0)"}), flush=True)
    sys.exit(1)
print(json.dumps({"evento": "collaudo", "esito": "superato",
                  "controllati": "centralBinom(0..5) = 1,2,6,20,70,252 e descFactorial"}),
      flush=True)

checkpoint = os.environ["RICERCA_CHECKPOINT"]
stato = os.environ["RICERCA_STATO"]
K_MAX = int(os.environ.get("K_MAX", "60"))
N_MAX = int(os.environ.get("N_MAX", "20000"))

k0 = 0
trovati = []
minimi = []
esaminati = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    k0 = d.get("posizione", 0)
    trovati = d.get("trovati", [])
    minimi = d.get("minimi", [])
    esaminati = d.get("esaminati", 0)

fermati = False
def arresto(s, f):
    global fermati
    fermati = True
signal.signal(signal.SIGTERM, arresto)
signal.signal(signal.SIGINT, arresto)

def salva(k):
    tmp = stato + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"posizione": k, "esaminati": esaminati, "trovati": trovati,
                   "minimi": minimi}, f)
    os.replace(tmp, stato)

t0 = time.time(); ultimo = t0
for k in range(k0, K_MAX + 1):
    if fermati:
        break
    trovato_n = None
    for n in range(k + 1, N_MAX):
        if central_binom(n) % desc_factorial(n, k + 1) == 0:
            trovato_n = n
            break
    esaminati += 1
    voce = {"k": k, "n_minimo": trovato_n}
    minimi.append(voce)
    if trovato_n is None:
        # NON e' un controesempio: la forma "per ogni k esiste n" non si
        # confuta con un calcolo. E' un indizio: fino a N_MAX non c'e' nessun n.
        trovati.append({"k": k, "nessun_n_fino_a": N_MAX,
                        "avvertenza": "indizio, non controesempio"})
    print(json.dumps({"evento": "progresso", "dettaglio": voce,
                      "posizione": k + 1, "esaminati": esaminati}), flush=True)
    ora = time.time()
    if ora - ultimo > 30:
        salva(k + 1); ultimo = ora

salva(k + 1 if not fermati else k)
print(json.dumps({"evento": "fine", "posizione": k, "esaminati": esaminati,
                  "secondi": round(time.time() - t0)}), flush=True)
'''



MURTHY = r'''
import json, os, signal, sys, time

from sympy import isprime

def esiste_k(n):
    """Il piu' piccolo k con k(n-k)-1 primo, o None se non esiste."""
    for k in range(1, n // 2 + 1):
        if isprime(k * (n - k) - 1):
            return k
    return None

# --- COLLAUDO su valori noti ------------------------------------------------
# I teoremi di prova dell'archivio (OEIS/109909.lean) fissano:
#   a(1)=0, a(2)=0, a(3)=0, a(4)=2  (numero di primi distinti k(n-k)-1)
# Qui basta la parte che serve alla ricerca: esiste k per n=4..8 e NON esiste
# per n=1,2,3.
attesi_senza = [1, 2, 3]
attesi_con = [4, 5, 6, 7, 8]
for n in attesi_senza:
    if esiste_k(n) is not None:
        print(json.dumps({"evento": "collaudo_fallito", "n": n,
                          "dettaglio": "trovato k dove l'archivio dice a(n)=0"}), flush=True)
        sys.exit(1)
for n in attesi_con:
    if esiste_k(n) is None:
        print(json.dumps({"evento": "collaudo_fallito", "n": n,
                          "dettaglio": "nessun k dove l'archivio dice a(n)>0"}), flush=True)
        sys.exit(1)
print(json.dumps({"evento": "collaudo", "esito": "superato",
                  "controllati": "n=1,2,3 senza k; n=4..8 con k, come i teoremi "
                                 "di prova dell'archivio"}), flush=True)

# --- ricerca ----------------------------------------------------------------
checkpoint = os.environ["RICERCA_CHECKPOINT"]
stato = os.environ["RICERCA_STATO"]
DA = int(os.environ.get("DA", "4"))
FINO_A = int(os.environ.get("FINO_A", "1000000000"))

inizio = DA
trovati = []
esaminati = 0
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    inizio = d.get("posizione", DA)
    trovati = d.get("trovati", [])
    esaminati = d.get("esaminati", 0)

fermati = False
def arresto(s, f):
    global fermati
    fermati = True
signal.signal(signal.SIGTERM, arresto)
signal.signal(signal.SIGINT, arresto)

def salva(n):
    tmp = stato + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"posizione": n, "esaminati": esaminati, "trovati": trovati,
                   "ultimo_n": n - 1}, fh)
    os.replace(tmp, stato)

print(json.dumps({"evento": "avvio", "da": inizio, "fino_a": FINO_A}), flush=True)
t0 = time.time()
ultimo_avviso = t0
n = inizio
while n < FINO_A and not fermati:
    if esiste_k(n) is None:
        trovati.append({"n": n, "nota": "nessun k con k(n-k)-1 primo: CONTROESEMPIO"})
        print(json.dumps({"evento": "trovato", "dettaglio": trovati[-1]}), flush=True)
    esaminati += 1
    n += 1
    ora = time.time()
    if ora - ultimo_avviso > 30:
        salva(n)
        print(json.dumps({"evento": "progresso", "posizione": n,
                          "esaminati": esaminati, "n_corrente": n,
                          "secondi": round(ora - t0)}), flush=True)
        ultimo_avviso = ora

salva(n)
print(json.dumps({"evento": "fine", "posizione": n, "esaminati": esaminati,
                  "trovati": len(trovati), "secondi": round(time.time() - t0)}),
      flush=True)
'''

RICERCHE = {
    "euclide_squarefree": {
        "problema": "EuclidNumbers.euclid_numbers_are_square_free",
        "programma": EUCLIDE,
        # MISURATO: 17984 primi (tutti sotto 200000) esaminati in 17 secondi,
        # nessun ritrovamento. Il costo cresce come il quadrato del limite,
        # quindi 2 milioni sono circa cento volte tanto: una mezz'ora.
        "variabili": {"LIMITE_P": 3000000},
        "descrizione": "cerca un primo p con p² che divide un numero di Euclide",
        "stato_noto": "aperto; non risulta una ricerca sistematica pubblicata",
        "conclusivo": "si: un solo p trovato confuta la congettura",
        # Che cosa finisce nella lista `trovati` del programma: veri
        # controesempi, oppure valori calcolati che vanno interpretati?
        "natura_trovati": "controesempi",
        # Come si legge un esito senza ritrovamenti, in termini matematici.
        # Si formatta con i campi dell'esito, le variabili della ricerca e
        # l'ultimo evento del registro.
        "esito_in_parole":
            "nessun primo p fino a {primo_corrente} ha p^2 che divide un numero "
            "di Euclide. Sono stati esaminati {esaminati} primi, e per ognuno "
            "TUTTI i primoriali con fattori minori di p: per quei p il "
            "controllo e' completo, non parziale.",
    },
    "erdos409_sigma": {
        "problema": "Erdos409.erdos_409.variants.sigma_prime_termination",
        "programma": SIGMA,
        "variabili": {"FINO_A": 200000, "MAX_PASSI": 200},
        "descrizione": "itera n -> sigma(n)-1 e cerca orbite che non toccano mai un primo",
        "stato_noto": "aperto",
        "conclusivo": "no: trova SOSPETTI, non controesempi. Un'orbita che non "
                      "raggiunge un primo in 200 passi va esaminata a mano",
        "natura_trovati": "sospetti",
        "esito_in_parole":
            "nessun n fino a {FINO_A} genera un'orbita di n -> sigma(n)-1 che "
            "eviti i numeri primi per {MAX_PASSI} passi.",
    },
    "murthy_kn_k": {
        "problema": "OeisA109909.conjecture",
        "programma": MURTHY,
        # MISURATO: 157 000 n/s a n circa 10^6 su un core (sympy.isprime, e il
        # primo k funziona quasi sempre). Un miliardo sono ~1,8 ore.
        "variabili": {"DA": 4, "FINO_A": 1000000000},
        "descrizione": "per ogni n > 3 cerca k con k(n-k)-1 primo; un n senza "
                       "k confuta la congettura di A. Murthy (2005)",
        "stato_noto": "aperta; citata nella raccolta di Zhi-Wei Sun "
                      "(arXiv:1211.1588) e in Niu-Zhang 2024. La frontiera "
                      "pubblicata non e' nota con precisione: questa ricerca "
                      "stabilisce almeno la nostra",
        "conclusivo": "si: un solo n senza k confuta la congettura, e per un n "
                      "moderato la confutazione si verifica anche in Lean",
        "natura_trovati": "controesempi",
        "esito_in_parole":
            "ogni n da 4 a {n_corrente} ha almeno un k con k(n-k)-1 primo: "
            "la congettura di Murthy regge fino a la'. Esaminati {esaminati} "
            "valori di n.",
    },
    "erdos396_binomiale": {
        "problema": "Erdos396.erdos_396",
        "programma": BINOMIALE,
        "variabili": {"K_MAX": 60, "N_MAX": 20000},
        "descrizione": "per ogni k, il piu' piccolo n con descFactorial(n,k+1) | centralBinom(n)",
        "stato_noto": "aperto",
        "conclusivo": "no: la forma e' 'per ogni k esiste n', che un calcolo non "
                      "puo' confutare. Serve a raccogliere indizi",
        "natura_trovati": "risultati calcolati",
        "esito_in_parole":
            "per ogni k fino a {K_MAX} si e' cercato il minimo n fino a {N_MAX} "
            "con descFactorial(n, k+1) che divide centralBinom(n).",
    },
}
