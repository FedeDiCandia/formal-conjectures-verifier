"""
Test del controllo sintattico preventivo (verifier/guard.py).

Sono test veloci: non fanno partire Lean. Servono a garantire two cose:
  * il guard NON da' falsi allarmi su code legittimo (altrimenti rifiuterebbe
    dimostrazioni valide, che e' l'error worst per l'utility' del system);
  * il guard blocca i costrutti pericolosi.
"""
import guard


# --- code legittimo: NON deve essere rifiutato ---------------------------

GOOD_CODE = {
    "dimostrazione normale": """
import FormalConjectures.Util.ProblemImports

namespace Esempio

@[category research solved, AMS 11]
theorem due_piu_due : 2 + 2 = 4 := by decide

end Esempio
""",
    "commento che nomina i costrutti vietati": """
-- Attenzione: qui NON usiamo sorry, ne' native_decide, ne' axiom.
/- Nemmeno in un commento a block: sorry, admit, #eval. -/
/-- Docstring: la word sorry compare ma e' only text. -/
theorem t : True := trivial
""",
    "identificatori che contengono le words vietate": """
theorem sorryFree_lemma : True := trivial
def axiomatic_thing : Nat := 0
theorem uses_admitted_style : True := trivial
""",
    "stringa contenente words vietate": '''
theorem t : True := by
  have msg := "sorry native_decide axiom"
  trivial
''',
    "set_option leciti": """
set_option maxHeartbeats 1000000 in
set_option maxRecDepth 4000 in
theorem t : True := trivial
""",
    "set_option usati dall'archive": """
set_option quotPrecheck false
theorem t : True := trivial
""",
    "decide +kernel e' lecito": """
-- `+kernel` fa controllare il KERNEL, il contrario di `+native`
theorem t : (2:Nat) + 2 = 4 := by decide +kernel
""",
    "other_items opzioni di tactic lecite": """
theorem t : True := by simp +arith +decide
""",
    "import leciti": """
import FormalConjectures.Util.ProblemImports
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import FormalConjecturesForMathlib.Combinatorics.Extra
theorem t : True := trivial
""",
}


def test_codice_legittimo_non_viene_rifiutato():
    for name, src in GOOD_CODE.items():
        r = guard.check_source(src)
        assert r.ok, f"falso allarme su «{name}»: {[str(f) for f in r.findings]}"


# --- code pericoloso: DEVE essere rifiutato ------------------------------

BAD_CODE = {
    "sorry":            ("theorem t : True := by sorry", "token:sorry"),
    "sorry annidato":   ("theorem t : True := by\n  have h : False := by sorry\n  trivial", "token:sorry"),
    "admit":            ("theorem t : True := by admit", "token:admit"),
    "axiom":            ("axiom imbroglio : False\ntheorem t : True := trivial", "command:axiom"),
    "native_decide":    ("theorem t : True := by native_decide", "token:native_decide"),
    "sorryAx diretto":  ("theorem t : True := sorryAx True", "token:sorryAx"),
    "skipKernelTC":     ("set_option debug.skipKernelTC true in\ntheorem t : True := trivial",
                         "option:debug.skipKernelTC"),
    "google.answer":    ("set_option google.answer postpone in\ntheorem t : True := trivial",
                         "option:google.answer"),
    "opzione ignota":   ("set_option qualcosa.di.strano true", "option:qualcosa.di.strano"),
    "#eval":            ('#eval IO.println "ciao"', "command:#eval"),
    "#exit":            ("#exit", "command:#exit"),
    "run_cmd":          ("run_cmd Lean.logInfo \"x\"", "command:run_cmd"),
    "macro":            ('macro "trucco" : term => `(1)', "command:macro"),
    "elab":             ('elab "trucco" : term => return default', "command:elab"),
    "unsafe":           ("unsafe def f : Nat := 0", "command:unsafe"),
    "implemented_by":   ("@[implemented_by other] def f : Nat := 0", "attribute:implemented_by"),
    "import Lean":      ("import Lean", "import"),
    "import del problem": ("import FormalConjectures.ErdosProblems.10", "import"),
}


def test_codice_pericoloso_viene_rifiutato():
    for name, (src, expected_rule) in BAD_CODE.items():
        r = guard.check_source(src)
        assert not r.ok, f"NON rifiutato: «{name}»"
        rules = {f.rule for f in r.findings}
        assert expected_rule in rules, \
            f"«{name}»: waited la rule {expected_rule}, found {rules}"


def test_i_numeri_di_riga_sono_corretti():
    src = "theorem a : True := trivial\ntheorem b : True := trivial\ntheorem c : True := by sorry\n"
    r = guard.check_source(src)
    assert not r.ok
    assert r.findings[0].line == 3, f"line waited 3, trovata {r.findings[0].line}"


def test_i_commenti_non_alterano_i_numeri_di_riga():
    src = "/- commento\n   su piu' lines\n   ancora -/\ntheorem t : True := by sorry\n"
    r = guard.check_source(src)
    assert not r.ok
    assert r.findings[0].line == 4, f"line waited 4, trovata {r.findings[0].line}"


# ---------------------------------------------------------------------------
# Costrutti che ESEGUONO CODE durante la compilazione
# ---------------------------------------------------------------------------
# Elenco ricavato leggendo i sorgenti di Lean 4.27
# (src/lean/Lean/Elab/BuiltinCommand.lean: gli `@[builtin_command_elab ...]`)
# e censendo gli attributi usati in Mathlib che registrano code eseguibile.
#
# Ognuno di questi PASSAVA il guard before di questo controllo: erano 19 buchi
# real_list, non ipotetici.

EXECUTABLE_CODE = {
    # --- commands
    "#eval!": ('#eval! IO.println "ciao"', "command:#eval!"),
    "run_meta": ("run_meta Lean.logInfo \"x\"", "command:run_meta"),
    "simproc": ("simproc miaProc (_ + 0) := fun e => return .continue", "command:simproc"),
    "simproc_decl": ("simproc_decl miaProc (_ + 0) := fun e => return .continue",
                     "command:simproc_decl"),
    "register_simp_attr": ("register_simp_attr mio_simp", "command:register_simp_attr"),
    "declare_syntax_cat": ("declare_syntax_cat miaCat", "command:declare_syntax_cat"),
    "notation3": ('notation3 "foo" => 1', "command:notation3"),
    "meta def": ("meta def cattivo : Unit := ()", "command:meta"),
    "public meta section": ("public meta section", "command:meta"),

    # --- attributi che registrano code presso un elaboratore o one tactic
    "@[simproc]": ("@[simproc] def p := 1", "attribute:simproc"),
    "@[tactic]": ("@[tactic myTac] def t := 1", "attribute:tactic"),
    "@[command_elab]": ("@[command_elab myCmd] def c := 1", "attribute:command_elab"),
    "@[term_elab]": ("@[term_elab myTerm] def e := 1", "attribute:term_elab"),
    "@[delab]": ("@[delab app.Foo] def d := 1", "attribute:delab"),
    "@[app_unexpander]": ("@[app_unexpander Foo] def u := 1", "attribute:app_unexpander"),
    "@[norm_num]": ("@[norm_num Nat.succ _] def n := 1", "attribute:norm_num"),
    "@[positivity]": ("@[positivity Foo _] def q := 1", "attribute:positivity"),
    "@[gcongr]": ("@[gcongr] def g := 1", "attribute:gcongr"),
    "@[fun_prop]": ("@[fun_prop] def f := 1", "attribute:fun_prop"),
    "@[export]": ("@[export mio_simbolo] def x := 1", "attribute:export"),

    # --- `decide +native` e' `native_decide` con la sintassi new: lascia lo
    # stesso assioma `Lean.ofReduceBool`. Non e' un caso ipotetico: 87
    # dimostrazioni dell'archive la usano.
    "decide +native": ("theorem t : True := by decide +native", "option:+native"),
    "decide+native": ("theorem t : True := by decide+native", "option:+native"),
    "simp +native": ("theorem t : True := by simp +native", "option:+native"),
    "@[init]": ("@[init mioInit] def y := 1", "attribute:init"),
    "attribute [simproc]": ("attribute [simproc] qualcosa", "attribute:simproc"),

    # --- dichiarazioni in one monade di elaborazione o di input/output.
    # E' il controllo STRUTTURALE: non insegue i commands one per one, ma
    # rifiuta il file che parla il linguaggio della metaprogrammazione.
    "def in IO": ("def cattivo : IO Unit := pure ()", "metaprogramming:IO"),
    "def in MetaM": ("def cattivo : MetaM Unit := pure ()", "metaprogramming:MetaM"),
    "def in CoreM": ("def cattivo : CoreM Unit := pure ()", "metaprogramming:CoreM"),
    "def in TacticM": ("def cattivo : TacticM Unit := pure ()", "metaprogramming:TacticM"),
    "def in CommandElabM": ("def c : CommandElabM Unit := pure ()",
                            "metaprogramming:CommandElabM"),
    "manipola Expr": ("def f (e : Expr) := e", "metaprogramming:Expr"),
    "manipola Syntax": ("def f (s : Syntax) := s", "metaprogramming:Syntax"),
    "open Lean Elab": ("open Lean Elab in\ndef f := 1", "metaprogramming:Elab"),
    "evalExpr": ("def f := evalExpr Nat q(Nat) e", "metaprogramming:evalExpr"),
}


def test_costrutti_che_eseguono_codice_vengono_rifiutati():
    """Ogni costrutto qui elencato passava il guard before di questo controllo."""
    non_bloccati = []
    wrong_rule = []
    for name, (src, expected_rule) in EXECUTABLE_CODE.items():
        r = guard.check_source(src)
        if r.ok:
            non_bloccati.append(name)
            continue
        if expected_rule not in {f.rule for f in r.findings}:
            wrong_rule.append((name, expected_rule, {f.rule for f in r.findings}))
    assert not non_bloccati, f"NON bloccati: {non_bloccati}"
    assert not wrong_rule, f"rule inattesa: {wrong_rule}"


def test_il_guard_non_disturba_i_file_veri_dell_archivio():
    """Il controllo piu' importante against i falsi allarmi: le rules sulla
    metaprogrammazione non devono scattare su nessuno dei file di problems
    dell'archive, che sono matematica ordinaria scritta da esseri umani."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "external" / "formal-conjectures"
    problems = root / "FormalConjectures"
    if not problems.is_dir():
        import pytest
        pytest.skip("archive non clonato")
    # Util/ e' metaprogrammazione per construction: e' giusto che venga segnalata
    files = [f for f in problems.rglob("*.lean") if "Util" not in f.parts]
    assert len(files) > 100, "mi aspetto centinaia di file di problems"

    culprits = []
    for f in files:
        r = guard.check_source(f.read_text(encoding="utf-8"))
        # `option:+native` NON va inclusa qui: e' un VERO positivo.
        # 87 dimostrazioni dell'archive usano `decide +native`, e il
        # verifier le rifiuta a ragione (lasciano l'assioma
        # Lean.ofReduceBool). Non e' un falso allarme: e' il reason per cui un
        # problem "gia' solved nell'archive" non e' detto sia risolvibile
        # below le nostre rules.
        new_items = [x for x in r.findings
                 if x.rule.startswith(("metaprogramming:", "attribute:"))
                 or x.rule in ("command:meta", "command:simproc", "command:run_meta",
                               "command:notation3")]
        if new_items:
            culprits.append((f.name, [x.rule for x in new_items]))
    assert not culprits, f"falsi allarmi su file real_list: {culprits[:5]}"
