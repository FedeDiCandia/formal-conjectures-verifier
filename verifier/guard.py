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
}

#: Attributi vietati: cambiano il codice eseguito, non la matematica.
BANNED_ATTRS: dict[str, str] = {
    "implemented_by": "`@[implemented_by]` sostituisce l'implementazione con altro codice",
    "extern": "`@[extern]` collega la dichiarazione a codice esterno",
    "csimp": "`@[csimp]` riscrive il codice compilato (rilevante per native_decide)",
    "never_extract": "attributo di basso livello non necessario a una dimostrazione",
}

#: Prefissi di `set_option` CONSENTITI. Tutto il resto e' rifiutato: e' una
#: lista bianca, cosi' un'opzione nuova o sconosciuta non passa per sbaglio.
ALLOWED_OPTION_PREFIXES: tuple[str, ...] = (
    "maxHeartbeats", "maxRecDepth", "maxSynthPendingDepth",
    "synthInstance.", "pp.", "trace.", "linter.", "profiler",
    "autoImplicit", "relaxedAutoImplicit", "tactic.", "grind.",
    "aesop.", "exponentiation.", "backward.", "warn.",
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

#: Moduli che il file candidato puo' importare.
ALLOWED_IMPORT_PREFIXES: tuple[str, ...] = (
    "FormalConjectures.Util.",
    "FormalConjecturesForMathlib",
    "Mathlib",
    "Batteries",
    "Aesop",
    "Qq",
    "Plausible",
    "Init",
    "Std",
)


def check_source(src: str) -> GuardReport:
    """Analizza il testo di un file Lean candidato."""
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
            if module and not module.startswith(ALLOWED_IMPORT_PREFIXES):
                add(idx, "import", f"import non consentito: `{module}`. Sono ammessi solo "
                                   f"i moduli di Mathlib e le utilita' dell'archivio "
                                   f"({', '.join(ALLOWED_IMPORT_PREFIXES[:3])}...). In particolare "
                                   f"NON si puo' importare il modulo del problema stesso.")

        # --- comandi vietati (a inizio riga, eventualmente dopo modificatori)
        head = re.sub(r"^(private|protected|public|noncomputable|scoped|local|meta|@\[[^\]]*\])\s+",
                      "", stripped)
        for cmd, why in BANNED_COMMANDS.items():
            if re.match(rf"^{re.escape(cmd)}(?!{_ID})", head):
                add(idx, f"comando:{cmd}", why)

        # --- attributi vietati
        for attr, why in BANNED_ATTRS.items():
            if re.search(rf"@\[[^\]]*(?<!{_ID}){re.escape(attr)}(?!{_ID})", line):
                add(idx, f"attributo:{attr}", why)

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


def check_file(path) -> GuardReport:
    with open(path, "r", encoding="utf-8") as f:
        return check_source(f.read())
