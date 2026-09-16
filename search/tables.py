"""
The tables of bounds, read from the source and put into a form a program can read.
program.

WHY
------
To beat a record one has to know **what it is**, **who set it** and **whether an
explicit code exists**. Brouwer's tables contain all three, but in hand-written
HTML. This file turns them into JSON and keeps the attributions: without the
attribution we cannot tell whether we are challenging work from 1990 on 1990
hardware or work from 2026 with a modern solver.

WHAT IT KEEPS FOR EACH CELL
----------------------------
  lower, upper       the known bounds (upper absent in the d=4 table)
  exact              true if the table marks a dot (the optimum is known)
  source             the superscript tag: empty = [BSSS] 1990
  construction       c = circulant, g = automorphism group, s = shortened
  code               the relative path of the explicit code, if there is one
  lost               true if the bound is in red: claimed but **the listing
                         of the code has been lost** and nobody has reconstructed it
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
    """Extract the cells of each table, keeping superscripts, links and classes."""

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
            self._c = {"text": "", "sup": "", "link": "", "lost": False,
                       "header": tag == "th"}
        elif tag == "sup":
            self._in_sup = True
        elif tag == "a" and self._c is not None and "href" in a:
            self._c["link"] = a["href"]
        elif tag == "span" and self._c is not None and a.get("class") == "lost":
            self._c["lost"] = True

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
    """Read a cell such as `232-276`, `80.`, `5616`, `≥ 40`."""
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
    # in the general table a numeric superscript is a power: `2` with sup `19`
    # means 2^19. Without this one reads 2 and believes the cell is empty.
    if tag.isdigit() and inf is not None and inf <= 9:
        inf = inf ** int(tag)
        tag = ""
    construction = "".join(ch for ch in tag if ch in CONSTRUCTIONS and len(tag) <= 2)
    source = tag if not construction else tag.replace(construction, "")
    return {"lower": inf, "upper": sup, "exact": exact,
            "source": source or "BSSS", "construction": construction,
            "code": cell["link"], "lost": cell["lost"]}


BASE = "https://aeb.win.tue.nl/codes/"


def _pagina(name: str) -> Path:
    """Brouwer's page, downloading it if it is not there.

    The pages are not versioned (they declare no licence): a clean clone does not
    have them, and this function puts them back. `curl` rather than urllib because
    this Mac's Python has no system certificates.
    """
    local = DATA_DIR / name
    if local.is_file() and local.stat().st_size > 0:
        return local
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["curl", "-sS", "-L", "--max-time", "45", "-A",
         "code-search/1.0 (independent check of published bounds)",
         "-o", str(local), BASE + name],
        capture_output=True, text=True)
    if result.returncode != 0 or not local.is_file() or local.stat().st_size == 0:
        local.unlink(missing_ok=True)
        raise OSError(f"cannot download {BASE + name}: "
                      f"{result.stderr.strip()[:120]}")
    return local


def constant_weight(path: Path | None = None) -> dict:
    """A(n,d,w): one table per d, rows n, columns w."""
    path = path or _pagina("Andw.html")
    text = path.read_text(errors="replace")
    # the <h1><a name="dK"> headings say which d the following table belongs to
    marcatori = [(m.start(), int(m.group(1)))
                 for m in re.finditer(r'<a name="d(\d+)"', text)]
    p = _Tabella()
    p.feed(text)
    # recompute each <table>'s position in order to pair it with its d
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
            continue   # not the bounds table (e.g. the lost-code one)
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
        # the header is `["", "", "d=4", "d=6", ...]`: one empty column of
        # spacing between the row's label and the data, present in the data too.
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
    (DATA_DIR / "bounds_cwc.json").write_text(json.dumps(cwc, indent=1, sort_keys=True))
    (DATA_DIR / "bounds_general.json").write_text(json.dumps(gen, indent=1, sort_keys=True))

    open_list = [k for k, v in cwc.items()
              if v["upper"] and v["upper"] > v["lower"]]
    print(f"A(n,d,w): {len(cwc)} cells, {len(open_list)} with an open gap")
    print(f"  with a downloadable explicit code: "
          f"{sum(1 for v in cwc.values() if v['code'])}")
    print(f"  lost bounds (no code reconstructed): "
          f"{[k for k, v in cwc.items() if v['lost']]}")
    from collections import Counter
    print("  sources of the lower bounds:",
          dict(Counter(v["source"] for v in cwc.values()).most_common(12)))
    apg = [k for k, v in gen.items()
           if v["upper"] and v["upper"] > v["lower"]]
    print(f"A(n,d): {len(gen)} cells, {len(apg)} with an open gap")


if __name__ == "__main__":
    main()
