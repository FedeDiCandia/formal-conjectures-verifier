"""
Test del controllo sintattico preventivo (verifier/guard.py).

Sono test veloci: non fanno partire Lean. Servono a garantire due cose:
  * il guard NON da' falsi allarmi su codice legittimo (altrimenti rifiuterebbe
    dimostrazioni valide, che e' l'errore peggiore per l'utilita' del sistema);
  * il guard blocca i costrutti pericolosi.
"""
import guard


# --- codice legittimo: NON deve essere rifiutato ---------------------------

CODICE_BUONO = {
    "dimostrazione normale": """
import FormalConjectures.Util.ProblemImports

namespace Esempio

@[category research solved, AMS 11]
theorem due_piu_due : 2 + 2 = 4 := by decide

end Esempio
""",
    "commento che nomina i costrutti vietati": """
-- Attenzione: qui NON usiamo sorry, ne' native_decide, ne' axiom.
/- Nemmeno in un commento a blocco: sorry, admit, #eval. -/
/-- Docstring: la parola sorry compare ma e' solo testo. -/
theorem t : True := trivial
""",
    "identificatori che contengono le parole vietate": """
theorem sorryFree_lemma : True := trivial
def axiomatic_thing : Nat := 0
theorem uses_admitted_style : True := trivial
""",
    "stringa contenente parole vietate": '''
theorem t : True := by
  have msg := "sorry native_decide axiom"
  trivial
''',
    "set_option leciti": """
set_option maxHeartbeats 1000000 in
set_option maxRecDepth 4000 in
theorem t : True := trivial
""",
    "import leciti": """
import FormalConjectures.Util.ProblemImports
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import FormalConjecturesForMathlib.Combinatorics.Extra
theorem t : True := trivial
""",
}


def test_codice_legittimo_non_viene_rifiutato():
    for nome, src in CODICE_BUONO.items():
        r = guard.check_source(src)
        assert r.ok, f"falso allarme su «{nome}»: {[str(f) for f in r.findings]}"


# --- codice pericoloso: DEVE essere rifiutato ------------------------------

CODICE_CATTIVO = {
    "sorry":            ("theorem t : True := by sorry", "token:sorry"),
    "sorry annidato":   ("theorem t : True := by\n  have h : False := by sorry\n  trivial", "token:sorry"),
    "admit":            ("theorem t : True := by admit", "token:admit"),
    "axiom":            ("axiom imbroglio : False\ntheorem t : True := trivial", "comando:axiom"),
    "native_decide":    ("theorem t : True := by native_decide", "token:native_decide"),
    "sorryAx diretto":  ("theorem t : True := sorryAx True", "token:sorryAx"),
    "skipKernelTC":     ("set_option debug.skipKernelTC true in\ntheorem t : True := trivial",
                         "opzione:debug.skipKernelTC"),
    "google.answer":    ("set_option google.answer postpone in\ntheorem t : True := trivial",
                         "opzione:google.answer"),
    "opzione ignota":   ("set_option qualcosa.di.strano true", "opzione:qualcosa.di.strano"),
    "#eval":            ('#eval IO.println "ciao"', "comando:#eval"),
    "#exit":            ("#exit", "comando:#exit"),
    "run_cmd":          ("run_cmd Lean.logInfo \"x\"", "comando:run_cmd"),
    "macro":            ('macro "trucco" : term => `(1)', "comando:macro"),
    "elab":             ('elab "trucco" : term => return default', "comando:elab"),
    "unsafe":           ("unsafe def f : Nat := 0", "comando:unsafe"),
    "implemented_by":   ("@[implemented_by altro] def f : Nat := 0", "attributo:implemented_by"),
    "import Lean":      ("import Lean", "import"),
    "import del problema": ("import FormalConjectures.ErdosProblems.10", "import"),
}


def test_codice_pericoloso_viene_rifiutato():
    for nome, (src, regola_attesa) in CODICE_CATTIVO.items():
        r = guard.check_source(src)
        assert not r.ok, f"NON rifiutato: «{nome}»"
        regole = {f.rule for f in r.findings}
        assert regola_attesa in regole, \
            f"«{nome}»: attesa la regola {regola_attesa}, trovate {regole}"


def test_i_numeri_di_riga_sono_corretti():
    src = "theorem a : True := trivial\ntheorem b : True := trivial\ntheorem c : True := by sorry\n"
    r = guard.check_source(src)
    assert not r.ok
    assert r.findings[0].line == 3, f"riga attesa 3, trovata {r.findings[0].line}"


def test_i_commenti_non_alterano_i_numeri_di_riga():
    src = "/- commento\n   su piu' righe\n   ancora -/\ntheorem t : True := by sorry\n"
    r = guard.check_source(src)
    assert not r.ok
    assert r.findings[0].line == 4, f"riga attesa 4, trovata {r.findings[0].line}"
