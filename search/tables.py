"""
Le tables dei bounds, lette dalla source e messe in forma leggibile da un
program.

PERCHÉ
------
Per battere un record bisogna sapere **qual è**, **chi l'ha fatto** e **se esiste
un code esplicito**. Le tables di Brouwer contengono all_items e three le cose, ma in
HTML fatto a mano. Questo file le trasforma in JSON, e conserva le attribuzioni:
senza l'attribuzione non sappiamo se stiamo sfidando un job del 1990 su
hardware del 1990 o un job del 2026 con un solutore moderno.

COSA CONSERVA PER OGNI CELLA
----------------------------
  inferiore, superiore   i bounds noti (superiore assente nella tabella d=4)
  exact                 vero se la tabella segna un punto (value ottimo noto)
  source                  la tag in esponente: vuota = [BSSS] 1990
  construction            c = circolante, g = group di automorfismi, s = accorciato
  code                 il path relative del code esplicito, se c'è
  perduto                vero se il limit è in rosso: rivendicato ma **il listato
                         del code è andato perduto** e nessuno l'ha ricostruito
"""
from __future__ import annotations

import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "research_data"

CONSTRUCTIONS = set("cgs")


class _Tabella(HTMLParser):
    """Estrae le cells di ogni tabella, conservando esponenti, link e classi."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[dict]]] = []
        self._t: list | None = None
        self._r: list | None = None
        self._c: dict | None = None
        self._in_sup = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._t = []
        elif tag == "tr" and self._t is not None:
            self._r = []
        elif tag in ("td", "th") and self._r is not None:
            self._c = {"text": "", "sup": "", "link": "", "perduto": False,
                       "header": tag == "th"}
        elif tag == "sup":
            self._in_sup = True
        elif tag == "a" and self._c is not None and "href" in a:
            self._c["link"] = a["href"]
        elif tag == "span" and self._c is not None and a.get("class") == "lost":
            self._c["perduto"] = True

    def handle_endtag(self, tag):
        if tag == "sup":
            self._in_sup = False
        elif tag in ("td", "th") and self._c is not None and self._r is not None:
            self._r.append(self._c)
            self._c = None
        elif tag == "tr" and self._r is not None and self._t is not None:
            self._t.append(self._r)
            self._r = None
        elif tag == "table" and self._t is not None:
            self.tables.append(self._t)
            self._t = None

    def handle_data(self, data):
        if self._c is None:
            return
        if self._in_sup:
            self._c["sup"] += data.strip()
        else:
            self._c["text"] += data


_NUM = re.compile(r"\d+")


def _limiti(text: str) -> tuple[int | None, int | None, bool]:
    """Legge one cell come `232-276`, `80.`, `5616`, `≥ 40`."""
    text = text.replace("–", "-").replace("−", "-").strip()
    exact = text.endswith(".")
    numbers = [int(x) for x in _NUM.findall(text)]
    if not numbers:
        return None, None, False
    if len(numbers) >= 2 and "-" in text:
        return numbers[0], numbers[1], exact
    return numbers[0], (numbers[0] if exact else None), exact


def _entry(cell: dict) -> dict | None:
    inf, sup, exact = _limiti(cell["text"])
    if inf is None:
        return None
    tag = cell["sup"] or ""
    # nella tabella generale un esponente numerico e' one potenza: `2` con sup `19`
    # vuol dire 2^19. Senza questo si legge 2 e si crede che la cell sia vuota.
    if tag.isdigit() and inf is not None and inf <= 9:
        inf = inf ** int(tag)
        tag = ""
    construction = "".join(ch for ch in tag if ch in CONSTRUCTIONS and len(tag) <= 2)
    source = tag if not construction else tag.replace(construction, "")
    return {"inferiore": inf, "superiore": sup, "exact": exact,
            "source": source or "BSSS", "construction": construction,
            "code": cell["link"], "perduto": cell["perduto"]}


BASE = "https://aeb.win.tue.nl/codes/"


def _pagina(name: str) -> Path:
    """La pagina di Brouwer, scaricandola se non c'e'.

    Le pagine non sono versionate (non dichiarano one licenza): un clone clean
    non le ha, e questa funzione le rimette dov'erano. `curl` e non urllib
    perche' il Python di questo Mac non ha i certificati di system.
    """
    local = DATA_DIR / name
    if local.is_file() and local.stat().st_size > 0:
        return local
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["curl", "-sS", "-L", "--max-time", "45", "-A",
         "ricerca-codici/1.0 (check indipendente di bounds pubblicati)",
         "-o", str(local), BASE + name],
        capture_output=True, text=True)
    if result.returncode != 0 or not local.is_file() or local.stat().st_size == 0:
        local.unlink(missing_ok=True)
        raise OSError(f"non riesco a scaricare {BASE + name}: "
                      f"{result.stderr.strip()[:120]}")
    return local


def constant_weight(path: Path | None = None) -> dict:
    """A(n,d,w): one tabella per ogni d, lines n, columns w."""
    path = path or _pagina("Andw.html")
    text = path.read_text(errors="replace")
    # i titoli <h1><a name="dK"> dicono a which d appartiene la tabella che segue
    marcatori = [(m.start(), int(m.group(1)))
                 for m in re.finditer(r'<a name="d(\d+)"', text)]
    p = _Tabella()
    p.feed(text)
    # ricalcolo la position di ogni <table> per associarla al suo d
    positions = [m.start() for m in re.finditer(r"<table", text)]
    assert len(positions) == len(p.tables), (len(positions), len(p.tables))

    outside: dict[str, dict] = {}
    for pos, tab in zip(positions, p.tables):
        d = None
        for mp, md in marcatori:
            if mp < pos:
                d = md
        if d is None or not tab:
            continue
        header = tab[0]
        if not header or "n\\w" not in header[0]["text"]:
            continue   # non è la tabella dei bounds (per es. quella del code perduto)
        weights = [int(c["text"]) for c in header[1:] if _NUM.search(c["text"])]
        for line in tab[1:]:
            if not line or not _NUM.search(line[0]["text"]):
                continue
            n = int(_NUM.search(line[0]["text"]).group())
            for w, cell in zip(weights, line[1:]):
                v = _entry(cell)
                if v:
                    outside[f"{n},{d},{w}"] = v
    return outside


def general(path: Path | None = None) -> dict:
    """A(n,d): lines n, columns d."""
    path = path or _pagina("binary-1.html")
    text = path.read_text(errors="replace")
    p = _Tabella()
    p.feed(text)
    outside: dict[str, dict] = {}
    for tab in p.tables:
        if not tab:
            continue
        # l'header e' `["", "", "d=4", "d=6", ...]`: one colonna vuota di
        # spaziatura fra l'label della line e i data, presente also nei data.
        head = [c["text"].strip() for c in tab[0]]
        first = next((i for i, t in enumerate(head) if t.startswith("d=")), None)
        if first is None:
            continue
        dd = [int(_NUM.search(t).group()) for t in head[first:] if _NUM.search(t)]
        for line in tab[1:]:
            if not line or not _NUM.search(line[0]["text"]):
                continue
            n = int(_NUM.search(line[0]["text"]).group())
            for d, cell in zip(dd, line[first:]):
                v = _entry(cell)
                if v:
                    outside[f"{n},{d}"] = v
    return outside


def main() -> None:
    cwc = constant_weight()
    gen = general()
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "limiti_cwc.json").write_text(json.dumps(cwc, indent=1, sort_keys=True))
    (DATA_DIR / "limiti_generali.json").write_text(json.dumps(gen, indent=1, sort_keys=True))

    open_list = [k for k, v in cwc.items()
              if v["superiore"] and v["superiore"] > v["inferiore"]]
    print(f"A(n,d,w): {len(cwc)} cells, {len(open_list)} con divario aperto")
    print(f"  con code esplicito scaricabile: "
          f"{sum(1 for v in cwc.values() if v['code'])}")
    print(f"  bounds perduti (nessun code ricostruito): "
          f"{[k for k, v in cwc.items() if v['perduto']]}")
    from collections import Counter
    print("  fonti dei bounds inferiori:",
          dict(Counter(v["source"] for v in cwc.values()).most_common(12)))
    apg = [k for k, v in gen.items()
           if v["superiore"] and v["superiore"] > v["inferiore"]]
    print(f"A(n,d): {len(gen)} cells, {len(apg)} con divario aperto")


if __name__ == "__main__":
    main()
