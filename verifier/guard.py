"""
Controllo sintattico preventivo del file candidato.

PERCHE' ESISTE
--------------
comparator (il "giudice" vero) garantisce le proprieta' LOGICHE: stesso
statement, only_ axioms permissions, accettazione da parte del kernel. Ma per
farlo deve COMPILARE il file candidato, e compilare un file Lean significa
eseguire code arbitrario (Lean ha `#eval`, macro, elaboratori...). Su Linux
comparator isola la compilazione con `landrun`; su macOS quella sandbox non
esiste.

Questo module e' la difesa in depth': legge il file PRIMA di compilarlo e
lo rifiuta se contiene costrutti che (a) non servono a one_ dimostrazione
onesta e (b) potrebbero eseguire code o confondere il confronto.

Nota: NON e' questo il controllo che rende affidabile il verifier. Un file
che passa di qui puo' ancora essere rifiutato da comparator. Il contrario non
deve mai succedere: qui blocchiamo only_ cose che comparator rifiuterebbe
comunque, oppure che sono pericolose per la macchina.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class GuardFinding:
    """Un problem found nel file."""
    line: int          # number di line (1-based)
    rule: str          # identificativo della rule_ violata
    detail: str        # explanation in italiano
    text: str          # la line incriminata

    def __str__(self) -> str:
        return f"line {self.line}: [{self.rule}] {self.detail}\n    | {self.text.strip()}"


@dataclass
class GuardReport:
    findings: list[GuardFinding] = field(default_factory=list)
    #: il code con commenti e stringhe neutralizzati (utile per debug)
    stripped: str = ""

    @property
    def ok(self) -> bool:
        return not self.findings


# ---------------------------------------------------------------------------
# 1. Neutralizzare commenti e stringhe
# ---------------------------------------------------------------------------
# Serve perche' la word "sorry" inside un commento o inside one_ stringa non
# e' un `sorry` vero. Sostituiamo il loro content con spazi, mantenendo la
# length e le andate a capo, cosi' i numbers di line restano corretti.

def strip_comments_and_strings(src: str) -> str:
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        # commento di line:  -- fino a end line
        if c == "-" and i + 1 < n and src[i + 1] == "-":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        # commento a block (annidabile):  /- ... -/   e also_ /-- ... -/
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
        # stringa "..."  (con escape \" )
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
# 2. Le rules
# ---------------------------------------------------------------------------

# Caratteri che possono far parte di un identificatore Lean. Serve a evitare
# falsi allarmi: `sorryFree` non deve far scattare la rule_ su `sorry`.
_ID = r"[A-Za-z0-9_'!?À-ɏͰ-Ͽ⁰-₟ᴀ-ᵿ]"

#: Come `_ID` ma senza `!` e `?`. Serve per i commands che iniziano con `#`:
#: `#eval!` e' un command diverso da `#eval`, e con `_ID` (che contiene `!`)
#: la ricerca di `#eval` non lo trovava — un buco vero, scoperto collaudando.
_ID_TAIL = r"[A-Za-z0-9_'À-ɏͰ-Ͽ⁰-₟ᴀ-ᵿ]"


def _token(word: str) -> re.Pattern:
    return re.compile(rf"(?<!{_ID})(?<!\.){re.escape(word)}(?!{_ID})")


#: Parole vietate ovunque nel code, con la explanation del perche'.
BANNED_TOKENS: dict[str, str] = {
    "sorry": "`sorry` lascia un buco nella dimostrazione (introduce l'assioma sorryAx)",
    "admit": "`admit` e' un sinonimo di `sorry`",
    "sorryAx": "`sorryAx` e' l'assioma prodotto da `sorry`",
    "native_decide": "`native_decide` delega il computation al compilatore, non al kernel "
                     "(introduce l'assioma Lean.ofReduceBool)",
    "ofReduceBool": "`Lean.ofReduceBool` e' l'assioma dietro `native_decide`",
    "trustCompiler": "`Lean.trustCompiler` chiede di fidarsi del compilatore",
}

#: Comandi vietati a start declaration. Sono all_of modi per eseguire code
#: durante la compilazione, oppure per introdurre new_ones verita' non dimostrate.
BANNED_COMMANDS: dict[str, str] = {
    "axiom": "one_ declaration `axiom` introduce one_ verita' non dimostrata",
    "#eval": "`#eval` esegue code arbitrario durante la compilazione",
    "#exit": "`#exit` interrompe l'elaborazione del file, nascondendo cio' che segue",
    "run_cmd": "`run_cmd` esegue code arbitrario durante la compilazione",
    "run_elab": "`run_elab` esegue code arbitrario durante la compilazione",
    "elab": "definire un elaboratore permette di alterare il significato del code",
    "elab_rules": "definire un elaboratore permette di alterare il significato del code",
    "macro": "definire one_ macro permette di alterare il significato del code",
    "macro_rules": "definire one_ macro permette di alterare il significato del code",
    "syntax": "definire new_ sintassi permette di alterare il significato del code",
    "initialize": "`initialize` esegue code al caricamento del module",
    "builtin_initialize": "`builtin_initialize` esegue code al caricamento del module",
    "unsafe": "`unsafe` disattiva i controlli di terminazione e sicurezza",
    "extern": "`extern` collega la declaration a code esterno",
    # --- added after aver letto i sorgenti di Lean 4.27 (Elab/BuiltinCommand.lean):
    # questi sono i commands che l'elaboratore record come esecutori di code.
    "meta": "`meta` mark code di metaprogrammazione, che gira durante la compilazione",
    "run_meta": "`run_meta` esegue code arbitrario in MetaM durante la compilazione",
    "#eval!": "`#eval!` esegue code arbitrario durante la compilazione",
    "simproc": "one_ simproc e' code che gira inside `simp`",
    "simproc_decl": "one_ simproc e' code che gira inside `simp`",
    "builtin_simproc": "one_ simproc e' code che gira inside `simp`",
    "register_simp_attr": "record un attributo che fa girare code inside `simp`",
    "declare_syntax_cat": "dichiarare one_ categoria sintattica serve only_ a definire new_ sintassi",
    "notation3": "e' one_ macro di Mathlib: altera il significato del code",
    "binderPredicate": "definisce new_ sintassi per i quantificatori",
}

#: Attributi vietati: cambiano il code eseguito, non la matematica.
BANNED_ATTRS: dict[str, str] = {
    "implemented_by": "`@[implemented_by]` sostituisce l'implementazione con other code",
    "extern": "`@[extern]` collega la declaration a code esterno",
    "csimp": "`@[csimp]` riscrive il code compilato (rilevante per native_decide)",
    "never_extract": "attributo di low level non necessario a one_ dimostrazione",
    # --- attributi che REGISTRANO code eseguibile presso un elaboratore o one_
    # tactic. Non si applicano mai a un lemma ordinario: per usarli bisogna
    # before aver scritto code di metaprogrammazione.
    "simproc": "`@[simproc]` record code che gira inside `simp`",
    "tactic": "`@[tactic]` record l'implementazione di one_ tactic",
    "command_elab": "`@[command_elab]` record un elaboratore di commands",
    "term_elab": "`@[term_elab]` record un elaboratore di termini",
    "builtin_command_elab": "record un elaboratore di commands",
    "builtin_term_elab": "record un elaboratore di termini",
    "builtin_tactic": "record l'implementazione di one_ tactic",
    "builtin_simproc": "record code che gira inside `simp`",
    "delab": "`@[delab]` record code per la show dei termini",
    "app_unexpander": "record code per la show dei termini",
    "norm_num": "`@[norm_num]` record un'estensione di `norm_num`, cioe' code",
    "positivity": "`@[positivity]` record un'estensione di `positivity`, cioe' code",
    "gcongr": "`@[gcongr]` record un'estensione di `gcongr`, cioe' code",
    "fun_prop": "`@[fun_prop]` record un'estensione di `fun_prop`, cioe' code",
    "macro": "`@[macro]` record one_ macro",
    "export": "`@[export]` espone la declaration al code nativo",
    "init": "`@[init]` fa eseguire code al caricamento del module",
    "builtin_init": "fa eseguire code al caricamento del module",
}

#: Nomi di kind_ che compaiono SOLO nel code di metaprogrammazione.
#: E' il controllo strutturale: invece di inseguire i commands one per one,
#: rifiutiamo il file che dichiara qualcosa in one_ monade di elaborazione o di
#: input/output. Una dimostrazione matematica non ne ha mai bisogno.
BANNED_META_TYPES: dict[str, str] = {
    "MetaM": "monade di metaprogrammazione",
    "CoreM": "monade di metaprogrammazione",
    "TermElabM": "monade dell'elaboratore di termini",
    "TacticM": "monade delle tattiche",
    "CommandElabM": "monade dell'elaboratore di commands",
    "MacroM": "monade delle macro",
    "AttrM": "monade degli attributi",
    "IO": "input/output: permette di leggere e scrivere file, non serve a one_ dimostrazione",
    "EIO": "input/output",
    "BaseIO": "input/output",
    "Simproc": "kind_ delle procedure di semplificazione",
    "NormNumExt": "estensione di `norm_num`, cioe' code",
    "PositivityExt": "estensione di `positivity`, cioe' code",
    "Expr": "rappresentazione interna dei termini: e' metaprogrammazione",
    "Syntax": "albero sintattico: e' metaprogrammazione",
    "TSyntax": "albero sintattico: e' metaprogrammazione",
    "Elab": "spazio dei names dell'elaboratore",
    "evalExpr": "valuta un termine come code compilato",
    "unsafeIO": "esegue input/output aggirando i controlli",
}

#: Prefissi di `set_option` CONSENTITI. Tutto il resto e' rifiutato: e' one_
#: list_ bianca, cosi' un'opzione new_ o sconosciuta non passa per sbaglio.
ALLOWED_OPTION_PREFIXES: tuple[str, ...] = (
    "maxHeartbeats", "maxRecDepth", "maxSynthPendingDepth",
    "synthInstance.", "pp.", "trace.", "linter.", "profiler",
    "autoImplicit", "relaxedAutoImplicit", "tactic.", "grind.",
    "aesop.", "exponentiation.", "backward.", "warn.",
    # `quotPrecheck` riguarda il controllo anticipato delle citazioni nelle
    # dichiarazioni di notazione: e' innocua e l'archive la usa davvero
    # (ErdosProblems/125.lean), quindi vietarla era un falso allarme.
    "quotPrecheck",
    # `hygiene` riguarda la cattura dei names nelle macro: non tocca il kernel.
    "hygiene",
)

#: Opzioni esplicitamente vietate, con explanation dedicata (hanno la
#: precedenza sulla list_ bianca).
BANNED_OPTIONS: dict[str, str] = {
    "debug.skipKernelTC": "disattiva il controllo del kernel: e' esattamente cio' "
                          "che rende one_ dimostrazione inaffidabile",
    "google.answer": "cambia il significato dell'elaboratore answer( ), quindi "
                     "l'statement stesso del problem",
    "compiler.enableNew": "riguarda il compilatore, non la matematica",
    "bootstrap.inductiveCheckResultingUniverse": "disattiva un controllo del kernel",
    "genInjectivity": "disattiva la generazione di theorems ausiliari",
    "structureDiamondWarning": "non pertinente",
}

#: Schemi vietati che non sono ne' words singole ne' commands: opzioni di
#: tactic, sintassi alternative degli stessi trucchi.
BANNED_PATTERNS: dict[str, tuple[str, str]] = {
    # `decide +native` e' la sintassi new_ di `native_decide`, e lascia lo
    # stesso assioma `Lean.ofReduceBool`. Scoperto leggendo l'archive: le sue
    # dimostrazioni di Selfridge.lean la usano, quindi il caso e' reale.
    "opzione:+native": (
        r"\+\s*native(?![A-Za-z0-9_'])",
        "l'opzione `+native` (per example `decide +native`) fa calcolare il "
        "compilatore invece del kernel: e' `native_decide` con un'altra "
        "sintassi e lascia lo stesso assioma `Lean.ofReduceBool`. "
        "Usa `decide` normale, oppure `decide +kernel`, che il kernel controlla."),
    "assioma:Lean.ofReduceNat": (
        r"(?<![A-Za-z0-9_'.])ofReduceNat(?![A-Za-z0-9_'])",
        "`Lean.ofReduceNat` e' un other assioma della valutazione compilata"),
    "opzione:set_option in stringa": (
        r"eval\s*%\[|evalExpr",
        "valutazione di code compilato"),
}

#: Moduli che il file candidato puo' importare.
ALLOWED_IMPORT_PREFIXES: tuple[str, ...] = (
    "FormalConjectures.Util.",
    # nel branch `main` le utility' sono diventate one_ libreria a se'
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
    """Analizza il text di un file Lean candidato.

    `allowed_module` consente UN singolo module in piu'. Serve alla mode'
    confutazione away `type_of%`: il candidato deve poter importare il module del
    problem per scrivere `¬ (type_of% @X)`, e non e' one_ scappatoia perche' in
    un problem aperto `X` e' dimostrato con `sorry`, quindi appoggiarsi alla sua
    dimostrazione introduce `sorryAx` e il controllo degli axioms lo rifiuta.

    `exploration=True` allenta UNA sola rule_: gli import. In un file di
    inspection importare il module del problem e' legittimo e utile — serve per
    fare `#print` sulle sue definizioni — mentre in one_ solution e' vietato,
    perche' dichiarerebbe un name che esiste gia'. Tutto il resto (niente
    code eseguibile, niente metaprogrammazione, niente opzioni pericolose)
    resta identico: un file di inspection viene compilato come qualunque other,
    quindi i rischi di esecuzione sono gli stessi.
    """
    report = GuardReport(stripped=strip_comments_and_strings(src))
    lines = report.stripped.split("\n")
    raw_lines = src.split("\n")

    def add(lineno: int, rule: str, detail: str) -> None:
        raw = raw_lines[lineno - 1] if 0 < lineno <= len(raw_lines) else ""
        report.findings.append(GuardFinding(lineno, rule, detail, raw))

    for idx, line in enumerate(lines, start=1):
        # --- words vietate
        for word, why in BANNED_TOKENS.items():
            if _token(word).search(line):
                add(idx, f"token:{word}", why)

        stripped = line.strip()

        # --- import
        if stripped.startswith("import "):
            module = stripped[len("import "):].strip()
            # `import all Foo` / `public import Foo` ecc.
            module = re.sub(r"^(all|public|meta|private)\s+", "", module).strip()
            allowed = (ALLOWED_IMPORT_PREFIXES + ("FormalConjectures",)
                          if exploration else ALLOWED_IMPORT_PREFIXES)
            if allowed_module:
                # one only_ (away type_of%) oppure one_ tupla (challenge libera, verify_free)
                added = ((allowed_module,) if isinstance(allowed_module, str)
                            else tuple(allowed_module))
                allowed = allowed + added
            if module and not module.startswith(allowed):
                add(idx, "import", f"import non consentito: `{module}`. Sono permitted only_ "
                                   f"i modules di Mathlib e le utility' dell'archive "
                                   f"({', '.join(ALLOWED_IMPORT_PREFIXES[:3])}...). In particolare "
                                   f"NON si puo' importare il module del problem stesso.")

        # --- commands vietati (a start line, eventualmente after modificatori)
        # NB: `meta` NON va tolto qui — e' esso stesso un command vietato
        # (mark il code di metaprogrammazione). Toglierlo lo rendeva invisibile.
        head = re.sub(r"^(private|protected|public|noncomputable|scoped|local|@\[[^\]]*\])\s+",
                      "", stripped)
        for cmd, why in BANNED_COMMANDS.items():
            queue = _ID_TAIL if cmd.startswith("#") else _ID
            if re.match(rf"^{re.escape(cmd)}(?!{queue})", head):
                add(idx, f"command:{cmd}", why)

        # --- `attribute [X] ...` puo' applicare un attributo vietato a posteriori
        for m in re.finditer(r"attribute\s*\[([^\]]*)\]", line):
            for attr, why in BANNED_ATTRS.items():
                if re.search(rf"(?<!{_ID}){re.escape(attr)}(?!{_ID})", m.group(1)):
                    add(idx, f"attributo:{attr}", why)

        # --- tipi di metaprogrammazione
        for kind_, why in BANNED_META_TYPES.items():
            if re.search(rf"(?<!{_ID})(?<!\.){re.escape(kind_)}(?!{_ID})", line):
                add(idx, f"metaprogrammazione:{kind_}",
                    f"il file nomina `{kind_}` ({why}). Una dimostrazione matematica non "
                    f"usa la metaprogrammazione: se davvero serve, va consentito "
                    f"consapevolmente in verifier/guard.py")

        # --- attributi vietati
        for attr, why in BANNED_ATTRS.items():
            if re.search(rf"@\[[^\]]*(?<!{_ID}){re.escape(attr)}(?!{_ID})", line):
                add(idx, f"attributo:{attr}", why)

        # --- schemi vietati (opzioni di tactic e sintassi alternative)
        for rule_, (schema, why) in BANNED_PATTERNS.items():
            if re.search(schema, line):
                add(idx, rule_, why)

        # --- set_option
        for m in re.finditer(r"set_option\s+([A-Za-z_][\w.']*)", line):
            opt = m.group(1)
            if opt in BANNED_OPTIONS:
                add(idx, f"opzione:{opt}", f"opzione vietata `{opt}`: {BANNED_OPTIONS[opt]}")
            elif not opt.startswith(ALLOWED_OPTION_PREFIXES):
                add(idx, f"opzione:{opt}", f"opzione `{opt}` non presente nella list_ bianca. "
                                           f"Se serve davvero, va aggiunta consapevolmente in "
                                           f"verifier/guard.py")

    return report


def check_file(path, *, exploration: bool = False,
               allowed_module: str | tuple[str, ...] | None = None) -> GuardReport:
    with open(path, "r", encoding="utf-8") as f:
        return check_source(f.read(), exploration=exploration,
                            allowed_module=allowed_module)
