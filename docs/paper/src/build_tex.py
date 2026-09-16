#!/usr/bin/env python3
"""Build the LaTeX note: write the values taken from the verification report, then
compile with tectonic and report missing glyphs and overfull boxes."""
import json
import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUB = HERE.parent
ROOT = PUB.parent.parent
REPORT = ROOT / "dati_ricerca" / "a105020_verifica_lean_en.json"
NUMBERS = {5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
ATTACHED = ("Solution.lean", "Challenge.lean", "config.json", "MeaningChecks.lean")


def main() -> None:
    challenge = PUB / "lean" / "Challenge.lean"
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if not report["esito"].upper().startswith("ACC"):
        raise SystemExit(f"verification report is not an acceptance: {report['esito']}")
    if REPORT.stat().st_mtime < max(challenge.stat().st_mtime,
                                    (PUB / "lean" / "Solution.lean").stat().st_mtime):
        raise SystemExit("verification report is older than the Lean files: re-verify first")
    n = len(json.loads((PUB / "lean" / "config.json").read_text())["theorem_names"])
    lines = len((PUB / "lean" / "Solution.lean").read_text(encoding="utf-8").splitlines())
    (PUB / "build").mkdir(exist_ok=True)
    (PUB / "build" / "values.tex").write_text(
        f"\\newcommand{{\\VerifySeconds}}{{{round(report['secondi'])}}}\n"
        f"\\newcommand{{\\SolutionLines}}{{{lines}}}\n"
        f"\\newcommand{{\\NumTheorems}}{{{NUMBERS.get(n, n)}}}\n", encoding="utf-8")
    result = subprocess.run(["tectonic", "--keep-logs", "--keep-intermediates",
                             "--outdir", "build", "A105020-goldbach.tex"],
                            cwd=PUB, capture_output=True, text=True)
    print(result.stdout[-3000:], result.stderr[-3000:])
    if result.returncode != 0:
        raise SystemExit("tectonic failed")
    log = (PUB / "build" / "A105020-goldbach.log").read_text(errors="replace")
    missing = sorted(set(re.findall(r"Missing character: There is no (.+?) in font", log)))
    overfull = re.findall(r"Overfull \\hbox \((\d+\.\d+)pt too wide\)[^\n]*lines (\d+)--(\d+)", log)
    print("missing glyphs:", missing or "none")
    print("overfull hboxes:", [(float(w), a, b) for w, a, b in overfull if float(w) > 1.0] or "none")
    (PUB / "build" / "A105020-goldbach.pdf").replace(PUB / "A105020-goldbach.pdf")
    print("wrote A105020-goldbach.pdf")
    tex = (PUB / "A105020-goldbach.tex").read_text(encoding="utf-8")
    problems = check_listings(PUB / "A105020-goldbach.pdf", tex)
    print("listings that do not read back from the PDF:", problems or "none")
    attachments = check_attachments(PUB / "A105020-goldbach.pdf")
    print("attachment problems:", attachments or "none")
    if problems or attachments:
        raise SystemExit("the PDF does not reproduce the code faithfully")


def check_attachments(pdf: Path) -> list[str]:
    """Extract the embedded files and compare them byte by byte with the sources."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdfdetach", "-saveall", "-o", tmp, str(pdf)], check=True,
                       capture_output=True)
        got = {p.name: p.read_bytes() for p in Path(tmp).iterdir()}
    problems = [f"{name}: {'missing' if name not in got else 'differs from the source'}"
                for name in ATTACHED if got.get(name) != (PUB / "lean" / name).read_bytes()]
    return problems + [f"{name}: unexpected attachment" for name in got if name not in ATTACHED]


def check_listings(pdf: Path, tex: str) -> list[str]:
    """Check that every listing reads back from the PDF text in the right order.
    Text extraction drops indentation and marks broken lines with ',→' or '↪'
    (depending on the math font), so the comparison ignores whitespace, those marks
    and the page numbers."""
    text = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True,
                          check=True).stdout
    lines = [re.sub(r"^\s*(,→|↪)", "", line) for line in text.replace("\f", "\n").split("\n")
             if not re.fullmatch(r"\s*\d+\s*", line)]
    blob = re.sub(r"\s+", "", "".join(lines))
    squeeze = lambda s: re.sub(r"\s+", "", s)
    sources = {name: (PUB / "lean" / name).read_text(encoding="utf-8") for name in ATTACHED}
    bodies = re.findall(r"\\begin\{lstlisting\}(?:\[[^\]]*\])?\n(.*?)\\end\{lstlisting\}",
                        tex, re.S)
    for i, body in enumerate(bodies, 1):
        sources[f"listing {i} in the text"] = body
    problems = []
    for name, source in sources.items():
        if squeeze(source) not in blob:
            bad = [line.strip() for line in source.splitlines()
                   if squeeze(line) and squeeze(line) not in blob]
            problems.append(f"{name}: {bad[0] if bad else 'lines out of order'}")
    return problems


if __name__ == "__main__":
    main()
