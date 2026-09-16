"""
Tests of the syntactic pre-scan (verifier/guard.py).

These are fast tests: they do not start Lean. They guarantee two things:
  * the guard does NOT raise false alarms on legitimate code (otherwise it would
      reject valid proofs, the worst error for the system's usefulness);
  * the guard blocks the dangerous constructs.
"""
import guard


# --- legitimate code: it must NOT be rejected -----------------------------

GOOD_CODE = {
    "an ordinary proof": """
import FormalConjectures.Util.ProblemImports

namespace Example

@[category research solved, AMS 11]
theorem two_plus_two : 2 + 2 = 4 := by decide

end Example
""",
    "a comment that names the forbidden constructs": """
-- Note: no sorry here, no native_decide, no axiom.
/- Not even in a block comment: sorry, admit, #eval. -/
/-- Docstring: the word sorry appears but it is only text. -/
theorem t : True := trivial
""",
    "identifiers that contain the forbidden words": """
theorem sorryFree_lemma : True := trivial
def axiomatic_thing : Nat := 0
theorem uses_admitted_style : True := trivial
""",
    "a string containing forbidden words": '''
theorem t : True := by
  have msg := "sorry native_decide axiom"
  trivial
''',
    "permitted set_option": """
set_option maxHeartbeats 1000000 in
set_option maxRecDepth 4000 in
theorem t : True := trivial
""",
    "set_option used by the archive": """
set_option quotPrecheck false
theorem t : True := trivial
""",
    "decide +kernel is allowed": """
-- `+kernel` makes the KERNEL check, the opposite of `+native`
theorem t : (2:Nat) + 2 = 4 := by decide +kernel
""",
    "other permitted tactic options": """
theorem t : True := by simp +arith +decide
""",
    "permitted imports": """
import FormalConjectures.Util.ProblemImports
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import FormalConjecturesForMathlib.Combinatorics.Extra
theorem t : True := trivial
""",
}


def test_legitimate_code_is_not_rejected():
    for name, src in GOOD_CODE.items():
        r = guard.check_source(src)
        assert r.ok, f"false alarm on «{name}»: {[str(f) for f in r.findings]}"


# --- dangerous code: it MUST be rejected ----------------------------------

BAD_CODE = {
    "sorry":            ("theorem t : True := by sorry", "token:sorry"),
    "nested sorry":     ("theorem t : True := by\n  have h : False := by sorry\n  trivial", "token:sorry"),
    "admit":            ("theorem t : True := by admit", "token:admit"),
    "axiom":            ("axiom imbroglio : False\ntheorem t : True := trivial", "command:axiom"),
    "native_decide":    ("theorem t : True := by native_decide", "token:native_decide"),
    "direct sorryAx":   ("theorem t : True := sorryAx True", "token:sorryAx"),
    "skipKernelTC":     ("set_option debug.skipKernelTC true in\ntheorem t : True := trivial",
                         "option:debug.skipKernelTC"),
    "google.answer":    ("set_option google.answer postpone in\ntheorem t : True := trivial",
                         "option:google.answer"),
    "unknown option":   ("set_option something.odd true", "option:something.odd"),
    "#eval":            ('#eval IO.println "hello"', "command:#eval"),
    "#exit":            ("#exit", "command:#exit"),
    "run_cmd":          ("run_cmd Lean.logInfo \"x\"", "command:run_cmd"),
    "macro":            ('macro "trick" : term => `(1)', "command:macro"),
    "elab":             ('elab "trick" : term => return default', "command:elab"),
    "unsafe":           ("unsafe def f : Nat := 0", "command:unsafe"),
    "implemented_by":   ("@[implemented_by other] def f : Nat := 0", "attribute:implemented_by"),
    "import Lean":      ("import Lean", "import"),
    "import del problem": ("import FormalConjectures.ErdosProblems.10", "import"),
}


def test_codice_pericoloso_viene_rifiutato():
    for name, (src, expected_rule) in BAD_CODE.items():
        r = guard.check_source(src)
        assert not r.ok, f"NOT rejected: «{name}»"
        rules = {f.rule for f in r.findings}
        assert expected_rule in rules, \
            f"«{name}»: expected the rule {expected_rule}, found {rules}"


def test_the_line_numbers_are_correct():
    src = "theorem a : True := trivial\ntheorem b : True := trivial\ntheorem c : True := by sorry\n"
    r = guard.check_source(src)
    assert not r.ok
    assert r.findings[0].line == 3, f"line waited 3, trovata {r.findings[0].line}"


def test_comments_do_not_shift_the_line_numbers():
    src = "/- a comment\n   over several lines\n   still going -/\ntheorem t : True := by sorry\n"
    r = guard.check_source(src)
    assert not r.ok
    assert r.findings[0].line == 4, f"line waited 4, trovata {r.findings[0].line}"


# ---------------------------------------------------------------------------
# Constructs that RUN CODE during compilation
# ---------------------------------------------------------------------------
# List drawn up by reading the Lean 4.27 sources
# (src/lean/Lean/Elab/BuiltinCommand.lean: the `@[builtin_command_elab ...]`)
# and by censusing the Mathlib attributes that register executable code.
#
# Every one of these GOT THROUGH the guard before this check: 19 real holes,
# not hypothetical ones.

EXECUTABLE_CODE = {
    # --- commands
    "#eval!": ('#eval! IO.println "hello"', "command:#eval!"),
    "run_meta": ("run_meta Lean.logInfo \"x\"", "command:run_meta"),
    "simproc": ("simproc myProc (_ + 0) := fun e => return .continue", "command:simproc"),
    "simproc_decl": ("simproc_decl myProc (_ + 0) := fun e => return .continue",
                     "command:simproc_decl"),
    "register_simp_attr": ("register_simp_attr mio_simp", "command:register_simp_attr"),
    "declare_syntax_cat": ("declare_syntax_cat myCat", "command:declare_syntax_cat"),
    "notation3": ('notation3 "foo" => 1', "command:notation3"),
    "meta def": ("meta def bad : Unit := ()", "command:meta"),
    "public meta section": ("public meta section", "command:meta"),

    # --- attributes that register code with an elaborator or a tactic
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

    # --- `decide +native` is `native_decide` in the new syntax: it leaves the
    # same axiom, `Lean.ofReduceBool`. Not hypothetical: 87 of the archive's
    # proofs use it.
    "decide +native": ("theorem t : True := by decide +native", "option:+native"),
    "decide+native": ("theorem t : True := by decide+native", "option:+native"),
    "simp +native": ("theorem t : True := by simp +native", "option:+native"),
    "@[init]": ("@[init myInit] def y := 1", "attribute:init"),
    "attribute [simproc]": ("attribute [simproc] something", "attribute:simproc"),

    # --- declarations in an elaboration or input/output monad.
    # This is the STRUCTURAL check: it does not chase the commands one at a time,
    # it rejects the file that speaks the language of metaprogramming.
    "def in IO": ("def bad : IO Unit := pure ()", "metaprogramming:IO"),
    "def in MetaM": ("def bad : MetaM Unit := pure ()", "metaprogramming:MetaM"),
    "def in CoreM": ("def bad : CoreM Unit := pure ()", "metaprogramming:CoreM"),
    "def in TacticM": ("def bad : TacticM Unit := pure ()", "metaprogramming:TacticM"),
    "def in CommandElabM": ("def c : CommandElabM Unit := pure ()",
                            "metaprogramming:CommandElabM"),
    "handles Expr": ("def f (e : Expr) := e", "metaprogramming:Expr"),
    "handles Syntax": ("def f (s : Syntax) := s", "metaprogramming:Syntax"),
    "open Lean Elab": ("open Lean Elab in\ndef f := 1", "metaprogramming:Elab"),
    "evalExpr": ("def f := evalExpr Nat q(Nat) e", "metaprogramming:evalExpr"),
}


def test_constructs_that_run_code_are_rejected():
    """Every construct listed here got through the guard before this check."""
    not_blocked = []
    wrong_rule = []
    for name, (src, expected_rule) in EXECUTABLE_CODE.items():
        r = guard.check_source(src)
        if r.ok:
            not_blocked.append(name)
            continue
        if expected_rule not in {f.rule for f in r.findings}:
            wrong_rule.append((name, expected_rule, {f.rule for f in r.findings}))
    assert not not_blocked, f"NOT blocked: {not_blocked}"
    assert not wrong_rule, f"unexpected rule: {wrong_rule}"


def test_the_guard_does_not_disturb_the_archives_real_files():
    """The most important check against false alarms: the metaprogramming rules
    must not fire on any of the archive's problem files, which are ordinary
    mathematics written by human beings."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "external" / "formal-conjectures"
    problems = root / "FormalConjectures"
    if not problems.is_dir():
        import pytest
        pytest.skip("archive not cloned")
    # Util/ is metaprogramming by construction: flagging it is correct
    files = [f for f in problems.rglob("*.lean") if "Util" not in f.parts]
    assert len(files) > 100, "hundreds of problem files are expected"

    culprits = []
    for f in files:
        r = guard.check_source(f.read_text(encoding="utf-8"))
        # `option:+native` must NOT be included here: it is a TRUE positive.
        # 87 of the archive's proofs use `decide +native`, and the verifier
        # rejects them rightly (they leave the axiom Lean.ofReduceBool).
        # It is not a false alarm: it is why a problem "already solved in the
        # archive" is not necessarily solvable under our rules.

        flagged = [x for x in r.findings
                   if x.rule.startswith(("metaprogramming:", "attribute:"))
                   or x.rule in ("command:meta", "command:simproc", "command:run_meta",
                                 "command:notation3")]
        if flagged:
            culprits.append((f.name, [x.rule for x in flagged]))
    assert not culprits, f"false alarms on real archive files: {culprits[:5]}"
