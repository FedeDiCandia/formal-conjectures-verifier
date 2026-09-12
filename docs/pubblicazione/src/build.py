#!/usr/bin/env python3
"""Build the note: inline the Lean files and the verification data into the Markdown
source, then render HTML with pandoc and PDF with headless Chrome."""
import json
import os
import re
import signal
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent            # docs/pubblicazione/src
PUB = HERE.parent                                  # docs/pubblicazione
ROOT = PUB.parent.parent
TEMPLATE = HERE / "A105020-goldbach.template.md"
OUT_MD = PUB / "A105020-goldbach.md"
OUT_HTML = PUB / "build" / "A105020-goldbach.html"
OUT_PDF = PUB / "A105020-goldbach.pdf"
REPORT = ROOT / "dati_ricerca" / "a105020_verifica_lean_en.json"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    text = re.sub(r"<!--INCLUDE:([^>]+)-->",
                  lambda m: (PUB / m.group(1)).read_text(encoding="utf-8").rstrip("\n"), text)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if not report["esito"].upper().startswith("ACC"):
        raise SystemExit(f"verification report is not an acceptance: {report['esito']}")
    solution_lines = len((PUB / "lean" / "Solution.lean").read_text(encoding="utf-8").splitlines())
    text = (text.replace("{{VERIFY_SECONDS}}", str(round(report["secondi"])))
                .replace("{{SOLUTION_LINES}}", str(solution_lines)))
    left = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if left:
        raise SystemExit(f"unfilled placeholders: {left}")
    OUT_MD.write_text(text, encoding="utf-8")
    OUT_HTML.parent.mkdir(exist_ok=True)
    subprocess.run(["pandoc", str(OUT_MD), "--from", "markdown", "--to", "html5",
                    "--standalone", "--embed-resources", "--mathml",
                    "--css", str(HERE / "style.css"), "-o", str(OUT_HTML)], check=True)
    # Headless Chrome on macOS writes the PDF and then does not always exit, so the
    # process is watched: once the file exists and its size is stable, Chrome is closed.
    OUT_PDF.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        proc = subprocess.Popen(
            [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
             "--no-default-browser-check", "--disable-extensions", "--disable-sync",
             "--disable-background-networking", f"--user-data-dir={profile}",
             "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
             "--virtual-time-budget=8000", f"--print-to-pdf={OUT_PDF}", OUT_HTML.as_uri()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        last, stable = -1, 0
        for _ in range(180):
            time.sleep(1)
            size = OUT_PDF.stat().st_size if OUT_PDF.exists() else -1
            stable = stable + 1 if (size > 0 and size == last) else 0
            last = size
            if stable >= 3 or proc.poll() is not None:
                break
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
    if not OUT_PDF.exists() or OUT_PDF.stat().st_size == 0:
        raise SystemExit("Chrome did not produce the PDF")
    print(f"wrote {OUT_MD.relative_to(ROOT)} and {OUT_PDF.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
