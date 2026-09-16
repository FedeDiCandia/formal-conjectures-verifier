"""
Syntactic pre-scan of the candidate file.

WHY IT EXISTS
-------------
comparator (the real judge) guarantees the LOGICAL properties: same statement,
permitted axioms only, acceptance by the kernel. But to do that it has to COMPILE
the candidate file, and compiling a Lean file means executing arbitrary code (Lean
has `#eval`, macros, elaborators…). On Linux comparator isolates compilation with
`landrun`; on macOS that sandbox does not exist.

This module is defence in depth: it reads the file BEFORE compiling it and rejects
it if it contains constructs that (a) an honest proof does not need and (b) could
execute code or confuse the comparison.

Note: this is NOT the check that makes the verifier trustworthy. A file that
passes here can still be rejected by comparator. The converse must never happen:
what is blocked here is only what comparator would reject anyway, or what is
dangerous to the machine.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class GuardFinding:
    """One problem found in the file."""
    line: int          # line number (1-based)
    rule: str          # identifier of the rule that was violated
    detail: str        # explanation
    text: str          # the offending line

    def __str__(self) -> str:
        return f"line {self.line}: [{self.rule}] {self.detail}\n    | {self.text.strip()}"


@dataclass
class GuardReport:
    findings: list[GuardFinding] = field(default_factory=list)
    #: the code with comments and strings neutralised (useful for debugging)
    stripped: str = ""

    @property
    def ok(self) -> bool:
        return not self.findings


# ---------------------------------------------------------------------------
# 1. Neutralise comments and strings
# ---------------------------------------------------------------------------
# This is needed because the word "sorry" inside a comment or a string is not a
# real `sorry`. Their content is replaced with spaces, keeping the length and the
# line breaks, so that line numbers stay correct.

def strip_comments_and_strings(src: str) -> str:
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        # line comment:  -- to the end of the line
        if c == "-" and i + 1 < n and src[i + 1] == "-":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        # block comment (nestable):  /- ... -/   and also /-- ... -/
        if c == "/" and i + 1 < n and src[i + 1] == "-":
            depth = 0
            while i < n:
                if src[i] == "/" and i + 1 < n and src[i + 1] == "-":
                    depth += 1
                    out.append("  "); i += 2; continue
                if src[i] == "-" and i + 1 < n and src[i + 1] == "/":
                    depth -= 1
                    out.append("  "); i += 2
                    if depth == 0:
                        break
                    continue
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            continue
        # string "..."  (with escaped \" )
        if c == '"':
            out.append(" "); i += 1
            while i < n:
                if src[i] == "\\" and i + 1 < n:
                    out.append("  "); i += 2; continue
                if src[i] == '"':
                    out.append(" "); i += 1; break
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# 2. The rules
# ---------------------------------------------------------------------------

# Characters that can be part of a Lean identifier. This avoids false alarms:
# `sorryFree` must not trigger the rule on `sorry`.
_ID = r"[A-Za-z0-9_'!?À-ɏͰ-Ͽ⁰-₟ᴀ-ᵿ]"

#: Like `_ID` but without `!` and `?`. Needed for the commands that start with
#: `#`: `#eval!` is a different command from `#eval`, and with `_ID` (which
#: contains `!`) the search for `#eval` missed it — a real hole, found by testing.
_ID_TAIL = r"[A-Za-z0-9_'À-ɏͰ-Ͽ⁰-₟ᴀ-ᵿ]"


def _token(word: str) -> re.Pattern:
    return re.compile(rf"(?<!{_ID})(?<!\.){re.escape(word)}(?!{_ID})")


#: Words forbidden anywhere in the code, with the reason why.
BANNED_TOKENS: dict[str, str] = {
    "sorry": "`sorry` leaves a hole in the proof (it introduces the axiom sorryAx)",
    "admit": "`admit` is a synonym for `sorry`",
    "sorryAx": "`sorryAx` is the axiom `sorry` produces",
    "native_decide": "`native_decide` hands the computation to the compiler rather than "
                     "the kernel (it introduces the axiom Lean.ofReduceBool)",
    "ofReduceBool": "`Lean.ofReduceBool` is the axiom behind `native_decide`",
    "trustCompiler": "`Lean.trustCompiler` asks you to trust the compiler",
}

#: Commands forbidden at the start of a declaration. They are all ways of running
#: code during compilation, or of introducing unproved truths.
BANNED_COMMANDS: dict[str, str] = {
    "axiom": "an `axiom` declaration introduces an unproved truth",
    "#eval": "`#eval` runs arbitrary code during compilation",
    "#exit": "`#exit` stops elaboration of the file, hiding whatever follows",
    "run_cmd": "`run_cmd` runs arbitrary code during compilation",
    "run_elab": "`run_elab` runs arbitrary code during compilation",
    "elab": "defining an elaborator allows the meaning of the code to be altered",
    "elab_rules": "defining an elaborator allows the meaning of the code to be altered",
    "macro": "defining a macro allows the meaning of the code to be altered",
    "macro_rules": "defining a macro allows the meaning of the code to be altered",
    "syntax": "defining new syntax allows the meaning of the code to be altered",
    "initialize": "`initialize` runs code when the module is loaded",
    "builtin_initialize": "`builtin_initialize` runs code when the module is loaded",
    "unsafe": "`unsafe` switches off the termination and safety checks",
    "extern": "`extern` links the declaration to external code",
    # --- added after reading the Lean 4.27 sources (Elab/BuiltinCommand.lean):
    # these are the commands the elaborator registers as code runners.
    "meta": "`meta` marks metaprogramming code, which runs during compilation",
    "run_meta": "`run_meta` runs arbitrary code in MetaM during compilation",
    "#eval!": "`#eval!` runs arbitrary code during compilation",
    "simproc": "a simproc is code that runs inside `simp`",
    "simproc_decl": "a simproc is code that runs inside `simp`",
    "builtin_simproc": "a simproc is code that runs inside `simp`",
    "register_simp_attr": "registers an attribute that makes code run inside `simp`",
    "declare_syntax_cat": "declaring a syntax category serves only to define new syntax",
    "notation3": "it is a Mathlib macro: it alters the meaning of the code",
    "binderPredicate": "defines new syntax for quantifiers",
}

#: Forbidden attributes: they change the code that runs, not the mathematics.
BANNED_ATTRS: dict[str, str] = {
    "implemented_by": "`@[implemented_by]` replaces the implementation with other code",
    "extern": "`@[extern]` links the declaration to external code",
    "csimp": "`@[csimp]` rewrites the compiled code (relevant to native_decide)",
    "never_extract": "a low-level attribute a proof has no need of",
    # --- attributes that REGISTER executable code with an elaborator or a
    # tactic. They never apply to an ordinary lemma: using them means having
    # written metaprogramming code first.
    "simproc": "`@[simproc]` registers code that runs inside `simp`",
    "tactic": "`@[tactic]` registers the implementation of a tactic",
    "command_elab": "`@[command_elab]` registers a command elaborator",
    "term_elab": "`@[term_elab]` registers a term elaborator",
    "builtin_command_elab": "registers a command elaborator",
    "builtin_term_elab": "registers a term elaborator",
    "builtin_tactic": "registers the implementation of a tactic",
    "builtin_simproc": "registers code that runs inside `simp`",
    "delab": "`@[delab]` registers code for displaying terms",
    "app_unexpander": "registers code for displaying terms",
    "norm_num": "`@[norm_num]` registers a `norm_num` extension, that is, code",
    "positivity": "`@[positivity]` registers a `positivity` extension, that is, code",
    "gcongr": "`@[gcongr]` registers a `gcongr` extension, that is, code",
    "fun_prop": "`@[fun_prop]` registers a `fun_prop` extension, that is, code",
    "macro": "`@[macro]` registers a macro",
    "export": "`@[export]` exposes the declaration to native code",
    "init": "`@[init]` makes code run when the module is loaded",
    "builtin_init": "makes code run when the module is loaded",
}

#: Type names that appear ONLY in metaprogramming code.
#: This is the structural check: instead of chasing commands one at a time, we
#: reject a file that declares anything in an elaboration or input/output monad.
#: A mathematical proof never needs one.
BANNED_META_TYPES: dict[str, str] = {
    "MetaM": "a metaprogramming monad",
    "CoreM": "a metaprogramming monad",
    "TermElabM": "the term elaborator's monad",
    "TacticM": "the tactics' monad",
    "CommandElabM": "the command elaborator's monad",
    "MacroM": "the macros' monad",
    "AttrM": "the attributes' monad",
    "IO": "input/output: it allows files to be read and written, which a proof does not need",
    "EIO": "input/output",
    "BaseIO": "input/output",
    "Simproc": "the type of simplification procedures",
    "NormNumExt": "a `norm_num` extension, that is, code",
    "PositivityExt": "a `positivity` extension, that is, code",
    "Expr": "the internal representation of terms: this is metaprogramming",
    "Syntax": "a syntax tree: this is metaprogramming",
    "TSyntax": "a syntax tree: this is metaprogramming",
    "Elab": "the elaborator's namespace",
    "evalExpr": "evaluates a term as compiled code",
    "unsafeIO": "performs input/output bypassing the checks",
}

#: ALLOWED `set_option` prefixes. Everything else is rejected: it is an
#: allow-list, so a new or unknown option cannot slip through by accident.
ALLOWED_OPTION_PREFIXES: tuple[str, ...] = (
    "maxHeartbeats", "maxRecDepth", "maxSynthPendingDepth",
    "synthInstance.", "pp.", "trace.", "linter.", "profiler",
    "autoImplicit", "relaxedAutoImplicit", "tactic.", "grind.",
    "aesop.", "exponentiation.", "backward.", "warn.",
    # `quotPrecheck` concerns early checking of quotations in notation
    # declarations: it is harmless and the archive really does use it
    # (ErdosProblems/125.lean), so forbidding it was a false alarm.
    "quotPrecheck",
    # `hygiene` concerns name capture in macros: it does not touch the kernel.
    "hygiene",
)

#: Options explicitly forbidden, with their own explanation (they take
#: precedence over the allow-list).
BANNED_OPTIONS: dict[str, str] = {
    "debug.skipKernelTC": "switches off the kernel check: precisely what makes a "
                          "proof untrustworthy",
    "google.answer": "changes the meaning of the answer( ) elaborator, and therefore "
                     "the statement of the problem itself",
    "compiler.enableNew": "concerns the compiler, not the mathematics",
    "bootstrap.inductiveCheckResultingUniverse": "switches off a kernel check",
    "genInjectivity": "switches off the generation of auxiliary theorems",
    "structureDiamondWarning": "not relevant",
}

#: Forbidden patterns that are neither single words nor commands: tactic
#: options, and alternative syntax for the same tricks.
BANNED_PATTERNS: dict[str, tuple[str, str]] = {
    # `decide +native` is the new syntax for `native_decide`, and it leaves the
    # same axiom, `Lean.ofReduceBool`. Found by reading the archive: its proofs in
    # Selfridge.lean use it, so the case is real.
    "option:+native": (
        r"\+\s*native(?![A-Za-z0-9_'])",
        "the `+native` option (for instance `decide +native`) makes the compiler "
        "do the computation instead of the kernel: it is `native_decide` in other "
        "syntax and leaves the same axiom, `Lean.ofReduceBool`. "
        "Use plain `decide`, or `decide +kernel`, which the kernel checks."),
    "axiom:Lean.ofReduceNat": (
        r"(?<![A-Za-z0-9_'.])ofReduceNat(?![A-Za-z0-9_'])",
        "`Lean.ofReduceNat` is another axiom of compiled evaluation"),
    "option:set_option in a string": (
        r"eval\s*%\[|evalExpr",
        "evaluation of compiled code"),
}

#: Modules the candidate file may import.
ALLOWED_IMPORT_PREFIXES: tuple[str, ...] = (
    "FormalConjectures.Util.",
    # on the `main` branch the utilities became a library of their own
    "FormalConjecturesUtil",
    "FormalConjecturesForMathlib",
    "Mathlib",
    "Batteries",
    "Aesop",
    "Qq",
    "Plausible",
    "Init",
    "Std",
)


def check_source(src: str, *, exploration: bool = False,
                 allowed_module: str | tuple[str, ...] | None = None) -> GuardReport:
    """Analyse the text of a candidate Lean file.

    `allowed_module` permits ONE extra module. It is needed by the refutation mode
    on the `type_of%` route: the candidate has to be able to import the problem's
    module in order to write `¬ (type_of% @X)`, and that is not a loophole because
    in an open problem `X` is proved with `sorry`, so leaning on its proof
    introduces `sorryAx` and the axiom check rejects it.

    `exploration=True` relaxes ONE rule only: imports. In an inspection file,
    importing the problem's module is legitimate and useful — it is how one runs
    `#print` on its definitions — whereas in a solution it is forbidden, because
    it would declare a name that already exists. Everything else (no executable
    code, no metaprogramming, no dangerous options) stays the same: an inspection
    file is compiled like any other, so the execution risks are identical.
    """
    report = GuardReport(stripped=strip_comments_and_strings(src))
    lines = report.stripped.split("\n")
    raw_lines = src.split("\n")

    def add(lineno: int, rule: str, detail: str) -> None:
        raw = raw_lines[lineno - 1] if 0 < lineno <= len(raw_lines) else ""
        report.findings.append(GuardFinding(lineno, rule, detail, raw))

    for idx, line in enumerate(lines, start=1):
        # --- forbidden words
        for word, why in BANNED_TOKENS.items():
            if _token(word).search(line):
                add(idx, f"token:{word}", why)

        stripped = line.strip()

        # --- import
        if stripped.startswith("import "):
            module = stripped[len("import "):].strip()
            # `import all Foo` / `public import Foo` and so on
            module = re.sub(r"^(all|public|meta|private)\s+", "", module).strip()
            allowed = (ALLOWED_IMPORT_PREFIXES + ("FormalConjectures",)
                          if exploration else ALLOWED_IMPORT_PREFIXES)
            if allowed_module:
                # a single one (outside type_of%) or a tuple (free challenge, verify_free)
                added = ((allowed_module,) if isinstance(allowed_module, str)
                            else tuple(allowed_module))
                allowed = allowed + added
            if module and not module.startswith(allowed):
                add(idx, "import", f"import not allowed: `{module}`. Only Mathlib's modules "
                                   f"and the archive's utilities are permitted "
                                   f"({', '.join(ALLOWED_IMPORT_PREFIXES[:3])}...). In particular "
                                   f"the problem's own module may NOT be imported.")

        # --- forbidden commands (at the start of a line, possibly after modifiers)
        # NB: `meta` must NOT be stripped here — it is itself a forbidden command
        # (it marks metaprogramming code). Stripping it made it invisible.
        head = re.sub(r"^(private|protected|public|noncomputable|scoped|local|@\[[^\]]*\])\s+",
                      "", stripped)
        for cmd, why in BANNED_COMMANDS.items():
            queue = _ID_TAIL if cmd.startswith("#") else _ID
            if re.match(rf"^{re.escape(cmd)}(?!{queue})", head):
                add(idx, f"command:{cmd}", why)

        # --- `attribute [X] ...` can apply a forbidden attribute after the fact
        for m in re.finditer(r"attribute\s*\[([^\]]*)\]", line):
            for attr, why in BANNED_ATTRS.items():
                if re.search(rf"(?<!{_ID}){re.escape(attr)}(?!{_ID})", m.group(1)):
                    add(idx, f"attribute:{attr}", why)

        # --- metaprogramming types
        for kind, why in BANNED_META_TYPES.items():
            if re.search(rf"(?<!{_ID})(?<!\.){re.escape(kind)}(?!{_ID})", line):
                add(idx, f"metaprogramming:{kind}",
                    f"the file names `{kind}` ({why}). A mathematical proof does not use "
                    f"metaprogramming: if it is genuinely needed, it has to be allowed "
                    f"deliberately in verifier/guard.py")

        # --- forbidden attributes
        for attr, why in BANNED_ATTRS.items():
            if re.search(rf"@\[[^\]]*(?<!{_ID}){re.escape(attr)}(?!{_ID})", line):
                add(idx, f"attribute:{attr}", why)

        # --- forbidden patterns (tactic options and alternative syntax)
        for rule, (schema, why) in BANNED_PATTERNS.items():
            if re.search(schema, line):
                add(idx, rule, why)

        # --- set_option
        for m in re.finditer(r"set_option\s+([A-Za-z_][\w.']*)", line):
            opt = m.group(1)
            if opt in BANNED_OPTIONS:
                add(idx, f"option:{opt}", f"forbidden option `{opt}`: {BANNED_OPTIONS[opt]}")
            elif not opt.startswith(ALLOWED_OPTION_PREFIXES):
                add(idx, f"option:{opt}", f"option `{opt}` is not on the allow-list. "
                                          f"If it is genuinely needed, it has to be added "
                                          f"deliberately in verifier/guard.py")

    return report


def check_file(path, *, exploration: bool = False,
               allowed_module: str | tuple[str, ...] | None = None) -> GuardReport:
    with open(path, "r", encoding="utf-8") as f:
        return check_source(f.read(), exploration=exploration,
                            allowed_module=allowed_module)
