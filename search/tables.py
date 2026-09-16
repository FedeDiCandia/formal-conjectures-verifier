"""
Le tabelle dei limiti, lette dalla fonte e messe in forma leggibile da un
programma.

PERCHÉ
------
Per battere un record bisogna sapere **qual è**, **chi l'ha fatto** e **se esiste
un codice esplicito**. Le tabelle di Brouwer contengono tutte e tre le cose, ma in
HTML fatto a mano. Questo file le trasforma in JSON, e conserva le attribuzioni:
senza l'attribuzione non sappiamo se stiamo sfidando un lavoro del 1990 su
hardware del 1990 o un lavoro del 2026 con un solutore moderno.

COSA CONSERVA PER OGNI CELLA
----------------------------
  inferiore, superiore   i limiti noti (superiore assente nella tabella d=4)
  esatto                 vero se la tabella segna un punto (valore ottimo noto)
  fonte                  la sigla in esponente: vuota = [BSSS] 1990
  costruzione            c = circolante, g = gruppo di automorfismi, s = accorciato
  codice                 il percorso relativo del codice esplicito, se c'è
  perduto                vero se il limite è in rosso: rivendicato ma **il listato
                         del codice è andato perduto** e nessuno l'ha ricostruito
"""
from __future__ import annotations

import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DATI = RADICE / "research_data"

COSTRUZIONI = set("cgs")


class _Tabella(HTMLParser):
    """Estrae le celle di ogni tabella, conservando esponenti, link e classi."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tabelle: list[list[list[dict]]] = []
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
            self._c = {"testo": "", "sup": "", "link": "", "perduto": False,
                       "intestazione": tag == "th"}
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
            self._c["testo"] += data


_NUM = re.compile(r"\d+")


def _limiti(testo: str) -> tuple[int | None, int | None, bool]:
    """Legge una cella come `232-276`, `80.`, `5616`, `≥ 40`."""
    testo = testo.replace("–", "-").replace("−", "-").strip()
    esatto = testo.endswith(".")
    numeri = [int(x) for x in _NUM.findall(testo)]
    if not numeri:
        return None, None, False
    if len(numeri) >= 2 and "-" in testo:
        return numeri[0], numeri[1], esatto
    return numeri[0], (numeri[0] if esatto else None), esatto


def _voce(cella: dict) -> dict | None:
    inf, sup, esatto = _limiti(cella["testo"])
    if inf is None:
        return None
    sigla = cella["sup"] or ""
    # nella tabella generale un esponente numerico e' una potenza: `2` con sup `19`
    # vuol dire 2^19. Senza questo si legge 2 e si crede che la cella sia vuota.
    if sigla.isdigit() and inf is not None and inf <= 9:
        inf = inf ** int(sigla)
        sigla = ""
    costruzione = "".join(ch for ch in sigla if ch in COSTRUZIONI and len(sigla) <= 2)
    fonte = sigla if not costruzione else sigla.replace(costruzione, "")
    return {"inferiore": inf, "superiore": sup, "esatto": esatto,
            "fonte": fonte or "BSSS", "costruzione": costruzione,
            "codice": cella["link"], "perduto": cella["perduto"]}


BASE = "https://aeb.win.tue.nl/codes/"


def _pagina(nome: str) -> Path:
    """La pagina di Brouwer, scaricandola se non c'e'.

    Le pagine non sono versionate (non dichiarano una licenza): un clone pulito
    non le ha, e questa funzione le rimette dov'erano. `curl` e non urllib
    perche' il Python di questo Mac non ha i certificati di sistema.
    """
    locale = DATI / nome
    if locale.is_file() and locale.stat().st_size > 0:
        return locale
    DATI.mkdir(parents=True, exist_ok=True)
    esito = subprocess.run(
        ["curl", "-sS", "-L", "--max-time", "45", "-A",
         "ricerca-codici/1.0 (verifica indipendente di limiti pubblicati)",
         "-o", str(locale), BASE + nome],
        capture_output=True, text=True)
    if esito.returncode != 0 or not locale.is_file() or locale.stat().st_size == 0:
        locale.unlink(missing_ok=True)
        raise OSError(f"non riesco a scaricare {BASE + nome}: "
                      f"{esito.stderr.strip()[:120]}")
    return locale


def peso_costante(percorso: Path | None = None) -> dict:
    """A(n,d,w): una tabella per ogni d, righe n, colonne w."""
    percorso = percorso or _pagina("Andw.html")
    testo = percorso.read_text(errors="replace")
    # i titoli <h1><a name="dK"> dicono a quale d appartiene la tabella che segue
    marcatori = [(m.start(), int(m.group(1)))
                 for m in re.finditer(r'<a name="d(\d+)"', testo)]
    p = _Tabella()
    p.feed(testo)
    # ricalcolo la posizione di ogni <table> per associarla al suo d
    posizioni = [m.start() for m in re.finditer(r"<table", testo)]
    assert len(posizioni) == len(p.tabelle), (len(posizioni), len(p.tabelle))

    fuori: dict[str, dict] = {}
    for pos, tab in zip(posizioni, p.tabelle):
        d = None
        for mp, md in marcatori:
            if mp < pos:
                d = md
        if d is None or not tab:
            continue
        intestazione = tab[0]
        if not intestazione or "n\\w" not in intestazione[0]["testo"]:
            continue   # non è la tabella dei limiti (per es. quella del codice perduto)
        pesi = [int(c["testo"]) for c in intestazione[1:] if _NUM.search(c["testo"])]
        for riga in tab[1:]:
            if not riga or not _NUM.search(riga[0]["testo"]):
                continue
            n = int(_NUM.search(riga[0]["testo"]).group())
            for w, cella in zip(pesi, riga[1:]):
                v = _voce(cella)
                if v:
                    fuori[f"{n},{d},{w}"] = v
    return fuori


def generali(percorso: Path | None = None) -> dict:
    """A(n,d): righe n, colonne d."""
    percorso = percorso or _pagina("binary-1.html")
    testo = percorso.read_text(errors="replace")
    p = _Tabella()
    p.feed(testo)
    fuori: dict[str, dict] = {}
    for tab in p.tabelle:
        if not tab:
            continue
        # l'intestazione e' `["", "", "d=4", "d=6", ...]`: una colonna vuota di
        # spaziatura fra l'etichetta della riga e i dati, presente anche nei dati.
        testa = [c["testo"].strip() for c in tab[0]]
        primo = next((i for i, t in enumerate(testa) if t.startswith("d=")), None)
        if primo is None:
            continue
        dd = [int(_NUM.search(t).group()) for t in testa[primo:] if _NUM.search(t)]
        for riga in tab[1:]:
            if not riga or not _NUM.search(riga[0]["testo"]):
                continue
            n = int(_NUM.search(riga[0]["testo"]).group())
            for d, cella in zip(dd, riga[primo:]):
                v = _voce(cella)
                if v:
                    fuori[f"{n},{d}"] = v
    return fuori


def main() -> None:
    cwc = peso_costante()
    gen = generali()
    DATI.mkdir(exist_ok=True)
    (DATI / "limiti_cwc.json").write_text(json.dumps(cwc, indent=1, sort_keys=True))
    (DATI / "limiti_generali.json").write_text(json.dumps(gen, indent=1, sort_keys=True))

    aperte = [k for k, v in cwc.items()
              if v["superiore"] and v["superiore"] > v["inferiore"]]
    print(f"A(n,d,w): {len(cwc)} celle, {len(aperte)} con divario aperto")
    print(f"  con codice esplicito scaricabile: "
          f"{sum(1 for v in cwc.values() if v['codice'])}")
    print(f"  limiti perduti (nessun codice ricostruito): "
          f"{[k for k, v in cwc.items() if v['perduto']]}")
    from collections import Counter
    print("  fonti dei limiti inferiori:",
          dict(Counter(v["fonte"] for v in cwc.values()).most_common(12)))
    apg = [k for k, v in gen.items()
           if v["superiore"] and v["superiore"] > v["inferiore"]]
    print(f"A(n,d): {len(gen)} celle, {len(apg)} con divario aperto")


if __name__ == "__main__":
    main()
