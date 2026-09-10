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


# ---------------------------------------------------------------------------
# Costrutti che ESEGUONO CODICE durante la compilazione
# ---------------------------------------------------------------------------
# Elenco ricavato leggendo i sorgenti di Lean 4.27
# (src/lean/Lean/Elab/BuiltinCommand.lean: gli `@[builtin_command_elab ...]`)
# e censendo gli attributi usati in Mathlib che registrano codice eseguibile.
#
# Ognuno di questi PASSAVA il guard prima di questo controllo: erano 19 buchi
# veri, non ipotetici.

CODICE_ESEGUIBILE = {
    # --- comandi
    "#eval!": ('#eval! IO.println "ciao"', "comando:#eval!"),
    "run_meta": ("run_meta Lean.logInfo \"x\"", "comando:run_meta"),
    "simproc": ("simproc miaProc (_ + 0) := fun e => return .continue", "comando:simproc"),
    "simproc_decl": ("simproc_decl miaProc (_ + 0) := fun e => return .continue",
                     "comando:simproc_decl"),
    "register_simp_attr": ("register_simp_attr mio_simp", "comando:register_simp_attr"),
    "declare_syntax_cat": ("declare_syntax_cat miaCat", "comando:declare_syntax_cat"),
    "notation3": ('notation3 "foo" => 1', "comando:notation3"),
    "meta def": ("meta def cattivo : Unit := ()", "comando:meta"),
    "public meta section": ("public meta section", "comando:meta"),

    # --- attributi che registrano codice presso un elaboratore o una tattica
    "@[simproc]": ("@[simproc] def p := 1", "attributo:simproc"),
    "@[tactic]": ("@[tactic myTac] def t := 1", "attributo:tactic"),
    "@[command_elab]": ("@[command_elab myCmd] def c := 1", "attributo:command_elab"),
    "@[term_elab]": ("@[term_elab myTerm] def e := 1", "attributo:term_elab"),
    "@[delab]": ("@[delab app.Foo] def d := 1", "attributo:delab"),
    "@[app_unexpander]": ("@[app_unexpander Foo] def u := 1", "attributo:app_unexpander"),
    "@[norm_num]": ("@[norm_num Nat.succ _] def n := 1", "attributo:norm_num"),
    "@[positivity]": ("@[positivity Foo _] def q := 1", "attributo:positivity"),
    "@[gcongr]": ("@[gcongr] def g := 1", "attributo:gcongr"),
    "@[fun_prop]": ("@[fun_prop] def f := 1", "attributo:fun_prop"),
    "@[export]": ("@[export mio_simbolo] def x := 1", "attributo:export"),
    "@[init]": ("@[init mioInit] def y := 1", "attributo:init"),
    "attribute [simproc]": ("attribute [simproc] qualcosa", "attributo:simproc"),

    # --- dichiarazioni in una monade di elaborazione o di input/output.
    # E' il controllo STRUTTURALE: non insegue i comandi uno per uno, ma
    # rifiuta il file che parla il linguaggio della metaprogrammazione.
    "def in IO": ("def cattivo : IO Unit := pure ()", "metaprogrammazione:IO"),
    "def in MetaM": ("def cattivo : MetaM Unit := pure ()", "metaprogrammazione:MetaM"),
    "def in CoreM": ("def cattivo : CoreM Unit := pure ()", "metaprogrammazione:CoreM"),
    "def in TacticM": ("def cattivo : TacticM Unit := pure ()", "metaprogrammazione:TacticM"),
    "def in CommandElabM": ("def c : CommandElabM Unit := pure ()",
                            "metaprogrammazione:CommandElabM"),
    "manipola Expr": ("def f (e : Expr) := e", "metaprogrammazione:Expr"),
    "manipola Syntax": ("def f (s : Syntax) := s", "metaprogrammazione:Syntax"),
    "open Lean Elab": ("open Lean Elab in\ndef f := 1", "metaprogrammazione:Elab"),
    "evalExpr": ("def f := evalExpr Nat q(Nat) e", "metaprogrammazione:evalExpr"),
}


def test_costrutti_che_eseguono_codice_vengono_rifiutati():
    """Ogni costrutto qui elencato passava il guard prima di questo controllo."""
    non_bloccati = []
    regola_sbagliata = []
    for nome, (src, regola_attesa) in CODICE_ESEGUIBILE.items():
        r = guard.check_source(src)
        if r.ok:
            non_bloccati.append(nome)
            continue
        if regola_attesa not in {f.rule for f in r.findings}:
            regola_sbagliata.append((nome, regola_attesa, {f.rule for f in r.findings}))
    assert not non_bloccati, f"NON bloccati: {non_bloccati}"
    assert not regola_sbagliata, f"regola inattesa: {regola_sbagliata}"


def test_il_guard_non_disturba_i_file_veri_dell_archivio():
    """Il controllo piu' importante contro i falsi allarmi: le regole sulla
    metaprogrammazione non devono scattare su nessuno dei file di problemi
    dell'archivio, che sono matematica ordinaria scritta da esseri umani."""
    import sys
    from pathlib import Path
    radice = Path(__file__).resolve().parent.parent / "external" / "formal-conjectures"
    problemi = radice / "FormalConjectures"
    if not problemi.is_dir():
        import pytest
        pytest.skip("archivio non clonato")
    # Util/ e' metaprogrammazione per costruzione: e' giusto che venga segnalata
    files = [f for f in problemi.rglob("*.lean") if "Util" not in f.parts]
    assert len(files) > 100, "mi aspetto centinaia di file di problemi"

    colpevoli = []
    for f in files:
        r = guard.check_source(f.read_text(encoding="utf-8"))
        nuove = [x for x in r.findings
                 if x.rule.startswith(("metaprogrammazione:", "attributo:"))
                 or x.rule in ("comando:meta", "comando:simproc", "comando:run_meta",
                               "comando:notation3")]
        if nuove:
            colpevoli.append((f.name, [x.rule for x in nuove]))
    assert not colpevoli, f"falsi allarmi su file veri: {colpevoli[:5]}"
