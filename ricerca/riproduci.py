"""
Passo zero della fase 1: **verificare in modo indipendente i record pubblicati.**

PERCHÉ QUESTO PRIMA DI CERCARE
------------------------------
Prima di provare a battere un record bisogna essere capaci di leggerlo e di
controllarlo. Se non riusciamo a verificare un codice che qualcuno ha già
pubblicato, non siamo in condizione di dire niente su uno che troviamo noi — ed è
esattamente l'errore che questo progetto ha già fatto cinque volte.

Questo script scarica i codici espliciti delle tabelle di Brouwer, li espande, li
verifica con il nostro giudice e confronta la dimensione con il limite inferiore
che la tabella rivendica. Tre esiti possibili, e tutti e tre sono informazione:

  CONFERMATO   la dimensione e la validità corrispondono alla tabella
  DISCORDE     il codice è valido ma di dimensione diversa da quella dichiarata
  NON VALIDO   il codice non soddisfa i vincoli (quasi certamente colpa nostra:
               un formato che non sappiamo leggere)

I file si scaricano una volta sola e restano in `dati_ricerca/codici/`.
"""
from __future__ import annotations

import json
import sys
import time
import subprocess
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "ricerca"))

from codici import Esito, leggi, verifica, verifica_veloce   # noqa: E402
from orbite import espandi, espandi_ciclico                  # noqa: E402

DATI = RADICE / "dati_ricerca"
CACHE = DATI / "codici"
BASE = "https://aeb.win.tue.nl/codes/"
PAUSA = 0.4      # cortesia verso un server universitario


def scarica(relativo: str) -> Path:
    locale = CACHE / relativo.replace("/", "_")
    if locale.is_file() and locale.stat().st_size > 0:
        return locale
    CACHE.mkdir(parents=True, exist_ok=True)
    # `curl` e non urllib: il Python di questo Mac non ha i certificati di
    # sistema e ogni https fallisce con CERTIFICATE_VERIFY_FAILED.
    esito = subprocess.run(
        ["curl", "-sS", "-L", "--max-time", "45", "-A",
         "ricerca-codici/1.0 (verifica indipendente di limiti pubblicati)",
         "-o", str(locale), BASE + relativo],
        capture_output=True, text=True)
    if esito.returncode != 0 or not locale.is_file() or locale.stat().st_size == 0:
        locale.unlink(missing_ok=True)
        raise OSError(f"curl ha fallito ({esito.returncode}): "
                      f"{esito.stderr.strip()[:120]}")
    time.sleep(PAUSA)
    return locale


def carica(percorso: Path) -> tuple[list[int], int, str]:
    """Legge un codice in qualunque dei formati in cui è pubblicato."""
    grezzo = percorso.read_text(errors="replace").lstrip()
    testa = grezzo[:200].lower()
    if testa.startswith("$base=16"):
        # elenco di parole in esadecimale
        parole = [int(r.strip(), 16) for r in grezzo.splitlines()[1:] if r.strip()]
        larghezza = max((len(r.strip()) for r in grezzo.splitlines()[1:] if r.strip()),
                        default=0)
        # la larghezza in cifre esadecimali non dice n: gli zeri in testa si
        # perdono. Si restituisce 0 e chi chiama usa l'n della cella.
        del larghezza
        return parole, 0, "elenco esadecimale"
    if testa.startswith("$exec orbit"):
        parole, n, info = espandi(percorso)
        return parole, n, f"orbite (|G|={info['ordine_gruppo']}, {info['semi']} semi)"
    if testa.startswith("$exec cycle"):
        parole, n, info = espandi_ciclico(percorso)
        return parole, n, (f"cicli {info['blocchi']} (|G|={info['ordine_gruppo']}, "
                           f"{info['semi']} semi)")
    if testa.startswith("$exec"):
        raise ValueError(f"comando $EXEC non gestito: {testa.splitlines()[0]!r}")
    parole, n = leggi(percorso)
    return parole, n, "elenco di parole"


def una(chiave: str, voce: dict) -> dict:
    n, d, w = (int(x) for x in chiave.split(","))
    esito = {"cella": f"A({n},{d},{w})", "atteso": voce["inferiore"],
             "fonte": voce["fonte"], "file": voce["codice"]}
    try:
        percorso = scarica(voce["codice"])
        parole, letto_n, formato = carica(percorso)
        esito["formato"] = formato
        if letto_n and letto_n != n:
            esito["stato"] = "DISCORDE"
            esito["nota"] = f"lunghezza letta {letto_n}, attesa {n}"
            return esito
        v = verifica_veloce(parole, n, d, w)
        esito["trovato"] = v.dimensione
        if not v.ok:
            esito["stato"] = "NON VALIDO"
            esito["nota"] = v.difetti[0]
        elif v.dimensione != voce["inferiore"]:
            esito["stato"] = "DISCORDE"
            esito["nota"] = (f"valido ma {v.dimensione} parole invece di "
                             f"{voce['inferiore']}")
        else:
            esito["stato"] = "CONFERMATO"
    except OSError as e:
        esito["stato"] = "NON SCARICATO"
        esito["nota"] = str(e)[:120]
    except Exception as e:                                   # noqa: BLE001
        esito["stato"] = "NON LETTO"
        esito["nota"] = f"{type(e).__name__}: {e}"[:160]
    return esito


def main() -> int:
    limiti = json.loads((DATI / "limiti_cwc.json").read_text())
    da_fare = {k: v for k, v in limiti.items() if v["codice"]}
    print(f"{len(da_fare)} celle con codice esplicito pubblicato.\n")
    esiti = []
    conta: dict[str, int] = {}
    for i, (k, v) in enumerate(sorted(da_fare.items(),
                                      key=lambda kv: kv[1]["inferiore"]), 1):
        e = una(k, v)
        esiti.append(e)
        conta[e["stato"]] = conta.get(e["stato"], 0) + 1
        marca = {"CONFERMATO": "ok", "DISCORDE": "??", "NON VALIDO": "XX"}.get(
            e["stato"], "--")
        print(f"[{i:3d}/{len(da_fare)}] {marca} {e['cella']:<14} "
              f"atteso {e['atteso']:>6}  "
              f"trovato {str(e.get('trovato', '-')):>6}  "
              f"{e.get('formato', '')}  {e.get('nota', '')}")
        sys.stdout.flush()
    (DATI / "riproduzione.json").write_text(json.dumps(esiti, indent=1))
    print("\n" + "=" * 70)
    for stato, quanti in sorted(conta.items(), key=lambda kv: -kv[1]):
        print(f"  {stato:<14} {quanti}")
    print(f"\nRapporto in {DATI / 'riproduzione.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
