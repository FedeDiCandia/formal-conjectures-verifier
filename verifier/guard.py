"""
Controllo sintattico preventivo del file candidato.

PERCHE' ESISTE
--------------
comparator (il "giudice" vero) garantisce le proprieta' LOGICHE: stesso
enunciato, solo assiomi permessi, accettazione da parte del kernel. Ma per
farlo deve COMPILARE il file candidato, e compilare un file Lean significa
eseguire codice arbitrario (Lean ha `#eval`, macro, elaboratori...). Su Linux
comparator isola la compilazione con `landrun`; su macOS quella sandbox non
esiste.

Questo modulo e' la difesa in profondita': legge il file PRIMA di compilarlo e
lo rifiuta se contiene costrutti che (a) non servono a una dimostrazione
onesta e (b) potrebbero eseguire codice o confondere il confronto.

Nota: NON e' questo il controllo che rende affidabile il verificatore. Un file
che passa di qui puo' ancora essere rifiutato da comparator. Il contrario non
deve mai succedere: qui blocchiamo solo cose che comparator rifiuterebbe
comunque, oppure che sono pericolose per la macchina.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class GuardFinding:
    """Un problema trovato nel file."""
    line: int          # numero di riga (1-based)
    rule: str          # identificativo della regola violata
    detail: str        # spiegazione in italiano
    text: str          # la riga incriminata

    def __str__(self) -> str:
        return f"riga {self.line}: [{self.rule}] {self.detail}\n    | {self.text.strip()}"


@dataclass
class GuardReport:
    findings: list[GuardFinding] = field(default_factory=list)
    #: il codice con commenti e stringhe neutralizzati (utile per debug)
    stripped: str = ""

    @property
    def ok(self) -> bool:
        return not self.findings


# ---------------------------------------------------------------------------
# 1. Neutralizzare commenti e stringhe
# ---------------------------------------------------------------------------
# Serve perche' la parola "sorry" dentro un commento o dentro una stringa non
# e' un `sorry` vero. Sostituiamo il loro contenuto con spazi, mantenendo la
# lunghezza e le andate a capo, cosi' i numeri di riga restano corretti.

def strip_comments_and_strings(src: str) -> str:
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        # commento di riga:  -- fino a fine riga
        if c == "-" and i + 1 < n and src[i + 1] == "-":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        # commento a blocco (annidabile):  /- ... -/   e anche /-- ... -/
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
# 2. Le regole
# ---------------------------------------------------------------------------

# Caratteri che possono far parte di un identificatore Lean. Serve a evitare
# falsi allarmi: `sorryFree` non deve far scattare la regola su `sorry`.
_ID = r"[A-Za-z0-9_'!?À-ɏͰ-Ͽ⁰-₟ᴀ-ᵿ]"

#: Come `_ID` ma senza `!` e `?`. Serve per i comandi che iniziano con `#`:
#: `#eval!` e' un comando diverso da `#eval`, e con `_ID` (che contiene `!`)
#: la ricerca di `#eval` non lo trovava — un buco vero, scoperto collaudando.
_ID_CODA = r"[A-Za-z0-9_'À-ɏͰ-Ͽ⁰-₟ᴀ-ᵿ]"


def _token(word: str) -> re.Pattern:
    return re.compile(rf"(?<!{_ID})(?<!\.){re.escape(word)}(?!{_ID})")


#: Parole vietate ovunque nel codice, con la spiegazione del perche'.
BANNED_TOKENS: dict[str, str] = {
    "sorry": "`sorry` lascia un buco nella dimostrazione (introduce l'assioma sorryAx)",
    "admit": "`admit` e' un sinonimo di `sorry`",
    "sorryAx": "`sorryAx` e' l'assioma prodotto da `sorry`",
    "native_decide": "`native_decide` delega il calcolo al compilatore, non al kernel "
                     "(introduce l'assioma Lean.ofReduceBool)",
    "ofReduceBool": "`Lean.ofReduceBool` e' l'assioma dietro `native_decide`",
    "trustCompiler": "`Lean.trustCompiler` chiede di fidarsi del compilatore",
}

#: Comandi vietati a inizio dichiarazione. Sono tutti modi per eseguire codice
#: durante la compilazione, oppure per introdurre nuove verita' non dimostrate.
BANNED_COMMANDS: dict[str, str] = {
    "axiom": "una dichiarazione `axiom` introduce una verita' non dimostrata",
    "#eval": "`#eval` esegue codice arbitrario durante la compilazione",
    "#exit": "`#exit` interrompe l'elaborazione del file, nascondendo cio' che segue",
    "run_cmd": "`run_cmd` esegue codice arbitrario durante la compilazione",
    "run_elab": "`run_elab` esegue codice arbitrario durante la compilazione",
    "elab": "definire un elaboratore permette di alterare il significato del codice",
    "elab_rules": "definire un elaboratore permette di alterare il significato del codice",
    "macro": "definire una macro permette di alterare il significato del codice",
    "macro_rules": "definire una macro permette di alterare il significato del codice",
    "syntax": "definire nuova sintassi permette di alterare il significato del codice",
    "initialize": "`initialize` esegue codice al caricamento del modulo",
    "builtin_initialize": "`builtin_initialize` esegue codice al caricamento del modulo",
    "unsafe": "`unsafe` disattiva i controlli di terminazione e sicurezza",
    "extern": "`extern` collega la dichiarazione a codice esterno",
    # --- aggiunti dopo aver letto i sorgenti di Lean 4.27 (Elab/BuiltinCommand.lean):
    # questi sono i comandi che l'elaboratore registra come esecutori di codice.
    "meta": "`meta` marca codice di metaprogrammazione, che gira durante la compilazione",
    "run_meta": "`run_meta` esegue codice arbitrario in MetaM durante la compilazione",
    "#eval!": "`#eval!` esegue codice arbitrario durante la compilazione",
    "simproc": "una simproc e' codice che gira dentro `simp`",
    "simproc_decl": "una simproc e' codice che gira dentro `simp`",
    "builtin_simproc": "una simproc e' codice che gira dentro `simp`",
    "register_simp_attr": "registra un attributo che fa girare codice dentro `simp`",
    "declare_syntax_cat": "dichiarare una categoria sintattica serve solo a definire nuova sintassi",
    "notation3": "e' una macro di Mathlib: altera il significato del codice",
    "binderPredicate": "definisce nuova sintassi per i quantificatori",
}

#: Attributi vietati: cambiano il codice eseguito, non la matematica.
BANNED_ATTRS: dict[str, str] = {
    "implemented_by": "`@[implemented_by]` sostituisce l'implementazione con altro codice",
    "extern": "`@[extern]` collega la dichiarazione a codice esterno",
    "csimp": "`@[csimp]` riscrive il codice compilato (rilevante per native_decide)",
    "never_extract": "attributo di basso livello non necessario a una dimostrazione",
    # --- attributi che REGISTRANO codice eseguibile presso un elaboratore o una
    # tattica. Non si applicano mai a un lemma ordinario: per usarli bisogna
    # prima aver scritto codice di metaprogrammazione.
    "simproc": "`@[simproc]` registra codice che gira dentro `simp`",
    "tactic": "`@[tactic]` registra l'implementazione di una tattica",
    "command_elab": "`@[command_elab]` registra un elaboratore di comandi",
    "term_elab": "`@[term_elab]` registra un elaboratore di termini",
    "builtin_command_elab": "registra un elaboratore di comandi",
    "builtin_term_elab": "registra un elaboratore di termini",
    "builtin_tactic": "registra l'implementazione di una tattica",
    "builtin_simproc": "registra codice che gira dentro `simp`",
    "delab": "`@[delab]` registra codice per la stampa dei termini",
    "app_unexpander": "registra codice per la stampa dei termini",
    "norm_num": "`@[norm_num]` registra un'estensione di `norm_num`, cioe' codice",
    "positivity": "`@[positivity]` registra un'estensione di `positivity`, cioe' codice",
    "gcongr": "`@[gcongr]` registra un'estensione di `gcongr`, cioe' codice",
    "fun_prop": "`@[fun_prop]` registra un'estensione di `fun_prop`, cioe' codice",
    "macro": "`@[macro]` registra una macro",
    "export": "`@[export]` espone la dichiarazione al codice nativo",
    "init": "`@[init]` fa eseguire codice al caricamento del modulo",
    "builtin_init": "fa eseguire codice al caricamento del modulo",
}

#: Nomi di tipo che compaiono SOLO nel codice di metaprogrammazione.
#: E' il controllo strutturale: invece di inseguire i comandi uno per uno,
#: rifiutiamo il file che dichiara qualcosa in una monade di elaborazione o di
#: input/output. Una dimostrazione matematica non ne ha mai bisogno.
BANNED_META_TYPES: dict[str, str] = {
    "MetaM": "monade di metaprogrammazione",
    "CoreM": "monade di metaprogrammazione",
    "TermElabM": "monade dell'elaboratore di termini",
    "TacticM": "monade delle tattiche",
    "CommandElabM": "monade dell'elaboratore di comandi",
    "MacroM": "monade delle macro",
    "AttrM": "monade degli attributi",
    "IO": "input/output: permette di leggere e scrivere file, non serve a una dimostrazione",
    "EIO": "input/output",
    "BaseIO": "input/output",
    "Simproc": "tipo delle procedure di semplificazione",
    "NormNumExt": "estensione di `norm_num`, cioe' codice",
    "PositivityExt": "estensione di `positivity`, cioe' codice",
    "Expr": "rappresentazione interna dei termini: e' metaprogrammazione",
    "Syntax": "albero sintattico: e' metaprogrammazione",
    "TSyntax": "albero sintattico: e' metaprogrammazione",
    "Elab": "spazio dei nomi dell'elaboratore",
    "evalExpr": "valuta un termine come codice compilato",
    "unsafeIO": "esegue input/output aggirando i controlli",
}

#: Prefissi di `set_option` CONSENTITI. Tutto il resto e' rifiutato: e' una
#: lista bianca, cosi' un'opzione nuova o sconosciuta non passa per sbaglio.
ALLOWED_OPTION_PREFIXES: tuple[str, ...] = (
    "maxHeartbeats", "maxRecDepth", "maxSynthPendingDepth",
    "synthInstance.", "pp.", "trace.", "linter.", "profiler",
    "autoImplicit", "relaxedAutoImplicit", "tactic.", "grind.",
    "aesop.", "exponentiation.", "backward.", "warn.",
    # `quotPrecheck` riguarda il controllo anticipato delle citazioni nelle
    # dichiarazioni di notazione: e' innocua e l'archivio la usa davvero
    # (ErdosProblems/125.lean), quindi vietarla era un falso allarme.
    "quotPrecheck",
    # `hygiene` riguarda la cattura dei nomi nelle macro: non tocca il kernel.
    "hygiene",
)

#: Opzioni esplicitamente vietate, con spiegazione dedicata (hanno la
#: precedenza sulla lista bianca).
BANNED_OPTIONS: dict[str, str] = {
    "debug.skipKernelTC": "disattiva il controllo del kernel: e' esattamente cio' "
                          "che rende una dimostrazione inaffidabile",
    "google.answer": "cambia il significato dell'elaboratore answer( ), quindi "
                     "l'enunciato stesso del problema",
    "compiler.enableNew": "riguarda il compilatore, non la matematica",
    "bootstrap.inductiveCheckResultingUniverse": "disattiva un controllo del kernel",
    "genInjectivity": "disattiva la generazione di teoremi ausiliari",
    "structureDiamondWarning": "non pertinente",
}

#: Schemi vietati che non sono ne' parole singole ne' comandi: opzioni di
#: tattica, sintassi alternative degli stessi trucchi.
BANNED_PATTERNS: dict[str, tuple[str, str]] = {
    # `decide +native` e' la sintassi nuova di `native_decide`, e lascia lo
    # stesso assioma `Lean.ofReduceBool`. Scoperto leggendo l'archivio: le sue
    # dimostrazioni di Selfridge.lean la usano, quindi il caso e' reale.
    "opzione:+native": (
        r"\+\s*native(?![A-Za-z0-9_'])",
        "l'opzione `+native` (per esempio `decide +native`) fa calcolare il "
        "compilatore invece del kernel: e' `native_decide` con un'altra "
        "sintassi e lascia lo stesso assioma `Lean.ofReduceBool`. "
        "Usa `decide` normale, oppure `decide +kernel`, che il kernel controlla."),
    "assioma:Lean.ofReduceNat": (
        r"(?<![A-Za-z0-9_'.])ofReduceNat(?![A-Za-z0-9_'])",
        "`Lean.ofReduceNat` e' un altro assioma della valutazione compilata"),
    "opzione:set_option in stringa": (
        r"eval\s*%\[|evalExpr",
        "valutazione di codice compilato"),
}

#: Moduli che il file candidato puo' importare.
ALLOWED_IMPORT_PREFIXES: tuple[str, ...] = (
    "FormalConjectures.Util.",
    # nel ramo `main` le utilita' sono diventate una libreria a se'
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


def check_source(src: str, *, esplorazione: bool = False) -> GuardReport:
    """Analizza il testo di un file Lean candidato.

    `esplorazione=True` allenta UNA sola regola: gli import. In un file di
    ispezione importare il modulo del problema e' legittimo e utile — serve per
    fare `#print` sulle sue definizioni — mentre in una soluzione e' vietato,
    perche' dichiarerebbe un nome che esiste gia'. Tutto il resto (niente
    codice eseguibile, niente metaprogrammazione, niente opzioni pericolose)
    resta identico: un file di ispezione viene compilato come qualunque altro,
    quindi i rischi di esecuzione sono gli stessi.
    """
    report = GuardReport(stripped=strip_comments_and_strings(src))
    lines = report.stripped.split("\n")
    raw_lines = src.split("\n")

    def add(lineno: int, rule: str, detail: str) -> None:
        raw = raw_lines[lineno - 1] if 0 < lineno <= len(raw_lines) else ""
        report.findings.append(GuardFinding(lineno, rule, detail, raw))

    for idx, line in enumerate(lines, start=1):
        # --- parole vietate
        for word, why in BANNED_TOKENS.items():
            if _token(word).search(line):
                add(idx, f"token:{word}", why)

        stripped = line.strip()

        # --- import
        if stripped.startswith("import "):
            module = stripped[len("import "):].strip()
            # `import all Foo` / `public import Foo` ecc.
            module = re.sub(r"^(all|public|meta|private)\s+", "", module).strip()
            consentiti = (ALLOWED_IMPORT_PREFIXES + ("FormalConjectures",)
                          if esplorazione else ALLOWED_IMPORT_PREFIXES)
            if module and not module.startswith(consentiti):
                add(idx, "import", f"import non consentito: `{module}`. Sono ammessi solo "
                                   f"i moduli di Mathlib e le utilita' dell'archivio "
                                   f"({', '.join(ALLOWED_IMPORT_PREFIXES[:3])}...). In particolare "
                                   f"NON si puo' importare il modulo del problema stesso.")

        # --- comandi vietati (a inizio riga, eventualmente dopo modificatori)
        # NB: `meta` NON va tolto qui — e' esso stesso un comando vietato
        # (marca il codice di metaprogrammazione). Toglierlo lo rendeva invisibile.
        head = re.sub(r"^(private|protected|public|noncomputable|scoped|local|@\[[^\]]*\])\s+",
                      "", stripped)
        for cmd, why in BANNED_COMMANDS.items():
            coda = _ID_CODA if cmd.startswith("#") else _ID
            if re.match(rf"^{re.escape(cmd)}(?!{coda})", head):
                add(idx, f"comando:{cmd}", why)

        # --- `attribute [X] ...` puo' applicare un attributo vietato a posteriori
        for m in re.finditer(r"attribute\s*\[([^\]]*)\]", line):
            for attr, why in BANNED_ATTRS.items():
                if re.search(rf"(?<!{_ID}){re.escape(attr)}(?!{_ID})", m.group(1)):
                    add(idx, f"attributo:{attr}", why)

        # --- tipi di metaprogrammazione
        for tipo, why in BANNED_META_TYPES.items():
            if re.search(rf"(?<!{_ID})(?<!\.){re.escape(tipo)}(?!{_ID})", line):
                add(idx, f"metaprogrammazione:{tipo}",
                    f"il file nomina `{tipo}` ({why}). Una dimostrazione matematica non "
                    f"usa la metaprogrammazione: se davvero serve, va consentito "
                    f"consapevolmente in verifier/guard.py")

        # --- attributi vietati
        for attr, why in BANNED_ATTRS.items():
            if re.search(rf"@\[[^\]]*(?<!{_ID}){re.escape(attr)}(?!{_ID})", line):
                add(idx, f"attributo:{attr}", why)

        # --- schemi vietati (opzioni di tattica e sintassi alternative)
        for regola, (schema, why) in BANNED_PATTERNS.items():
            if re.search(schema, line):
                add(idx, regola, why)

        # --- set_option
        for m in re.finditer(r"set_option\s+([A-Za-z_][\w.']*)", line):
            opt = m.group(1)
            if opt in BANNED_OPTIONS:
                add(idx, f"opzione:{opt}", f"opzione vietata `{opt}`: {BANNED_OPTIONS[opt]}")
            elif not opt.startswith(ALLOWED_OPTION_PREFIXES):
                add(idx, f"opzione:{opt}", f"opzione `{opt}` non presente nella lista bianca. "
                                           f"Se serve davvero, va aggiunta consapevolmente in "
                                           f"verifier/guard.py")

    return report


def check_file(path, *, esplorazione: bool = False) -> GuardReport:
    with open(path, "r", encoding="utf-8") as f:
        return check_source(f.read(), esplorazione=esplorazione)
