"""
Esecuzione di ricerche lunghe, isolate, con checkpoint e ripresa.

A COSA SERVE
------------
Cercare un controesempio a una congettura puo' richiedere ore o giorni. Una
ricerca del genere ha tre esigenze che uno script normale non copre:

  * ISOLAMENTO — il programma di ricerca e' scritto da un modello linguistico e
    non ha motivo di toccare la rete o il resto del disco. Gira dentro
    `sandbox-exec`, come tutto il resto del progetto.
  * CHECKPOINT — se il computer si spegne dopo sei ore, ricominciare da capo e'
    inaccettabile. Il programma salva a intervalli regolari a che punto e'
    arrivato, e alla ripartenza riprende da li'.
  * RESOCONTO — una ricerca che non trova niente non e' un fallimento: dice
    "fino a N non c'e' nulla", che e' un'informazione. Va registrata.

Il programma di ricerca deve rispettare un piccolo contratto, descritto in
`CONTRATTO` qui sotto: legge da dove ripartire, stampa i progressi in JSON,
e si ferma con garbo quando riceve il segnale di arresto.
"""
from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import sandbox


CONTRATTO = """
CONTRATTO DEL PROGRAMMA DI RICERCA
==================================
Il tuo programma riceve due variabili d'ambiente:

  RICERCA_CHECKPOINT  percorso di un file JSON. Se esiste, contiene il punto
                      da cui ripartire, nella forma che hai deciso tu.
  RICERCA_STATO       percorso su cui SCRIVERE il checkpoint aggiornato.

Devi:

1. All'avvio, se RICERCA_CHECKPOINT esiste, leggerlo e ripartire da li'.
   Altrimenti partire dall'inizio.

2. Ogni tanto (almeno ogni 30 secondi) scrivere su RICERCA_STATO un JSON con
   almeno questi campi:
       {"posizione": <dove sei arrivato>, "esaminati": <quanti casi>,
        "trovati": [<eventuali risultati>]}
   Scrivilo prima su un file temporaneo e poi rinominalo, cosi' un'interruzione
   a meta' non lascia un checkpoint corrotto.

3. Stampare su stdout una riga JSON per ogni avanzamento importante:
       {"evento": "progresso", "posizione": ..., "esaminati": ...}
       {"evento": "trovato", "dettaglio": {...}}
   Le righe che non sono JSON valido vengono conservate nel log ma ignorate.

4. Gestire SIGTERM: salvare il checkpoint e uscire con codice 0.
   Il contenitore ti manda SIGTERM quando l'utente ferma la ricerca.

5. Non usare la rete (e' bloccata) e non scrivere fuori dalla tua cartella.
"""


@dataclass
class EsitoRicerca:
    nome: str
    conclusa: bool = False
    interrotta: bool = False
    secondi: float = 0.0
    posizione: object = None
    esaminati: int = 0
    trovati: list = field(default_factory=list)
    codice_uscita: int | None = None
    errore: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, default=str)


class Ricerca:
    """Una ricerca lunga, isolata, ripartibile."""

    def __init__(self, nome: str, programma: str, cartella: Path | None = None,
                 interprete: Path | None = None, variabili: dict | None = None):
        self.nome = nome
        self.programma = programma
        #: Parametri passati al programma come variabili d'ambiente.
        #: L'ambiente del processo figlio e' volutamente minimo (nessuna chiave
        #: API, nessun PATH del progetto), quindi i parametri vanno passati
        #: esplicitamente qui: quello che sta nell'ambiente di chi lancia NON
        #: arriva al programma di ricerca.
        self.variabili = dict(variabili or {})
        self.cartella = (cartella or (config.ROOT / "runs" / "caccia" / nome))
        self.cartella.mkdir(parents=True, exist_ok=True)
        #: l'ambiente di calcolo, con numpy, sympy e numba
        self.interprete = interprete or (config.ROOT / ".venv-calcolo" / "bin" / "python")
        if not self.interprete.is_file():
            self.interprete = Path(sys.base_prefix) / "bin" / "python3"

    # --- file
    @property
    def file_programma(self) -> Path:
        return self.cartella / "programma.py"

    @property
    def file_checkpoint(self) -> Path:
        return self.cartella / "checkpoint.json"

    @property
    def file_log(self) -> Path:
        return self.cartella / "ricerca.log"

    @property
    def file_esito(self) -> Path:
        return self.cartella / "esito.json"

    # --- esecuzione
    def _profilo(self, tmp: Path) -> Path | None:
        if not (config.USA_SANDBOX and sandbox.disponibile()):
            return None
        scrivibili = [self.cartella, tmp]
        for d in scrivibili:
            d.mkdir(parents=True, exist_ok=True)
        return sandbox.scrivi_profilo(tmp / "ricerca.sb", scrivibili, config.ROOT)

    def esegui(self, *, secondi_massimi: float | None = None,
               riprendi: bool = True, verboso: bool = True) -> EsitoRicerca:
        self.file_programma.write_text(self.programma, encoding="utf-8")
        esito = EsitoRicerca(nome=self.nome)

        if not riprendi:
            self.file_checkpoint.unlink(missing_ok=True)

        stato_nuovo = self.cartella / "stato.json"
        ambiente = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.cartella),
            "TMPDIR": str(self.cartella),
            "LANG": "C.UTF-8",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "RICERCA_CHECKPOINT": str(self.file_checkpoint),
            "RICERCA_STATO": str(stato_nuovo),
        }
        ambiente.update({k: str(v) for k, v in self.variabili.items()})

        import tempfile
        with tempfile.TemporaryDirectory(prefix=f"ricerca_{self.nome}_") as tmp:
            tmp_dir = Path(tmp)
            profilo = self._profilo(tmp_dir)
            comando = [str(self.interprete), "-u", str(self.file_programma)]
            if profilo is not None:
                comando = sandbox.avvolgi(comando, profilo)

            avvio = time.time()
            with open(self.file_log, "a", encoding="utf-8") as log:
                log.write(f"\n=== avvio {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                log.flush()
                proc = subprocess.Popen(
                    comando, cwd=str(self.cartella), env=ambiente,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, start_new_session=True, bufsize=1)

                def termina(_s=None, _f=None):
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass

                originale = signal.getsignal(signal.SIGTERM)
                try:
                    signal.signal(signal.SIGTERM, termina)
                except ValueError:
                    pass   # non siamo nel thread principale

                try:
                    for riga in proc.stdout:
                        log.write(riga)
                        log.flush()
                        riga = riga.strip()
                        if verboso and riga:
                            print(f"  [{self.nome}] {riga[:150]}", flush=True)
                        try:
                            evento = json.loads(riga)
                        except Exception:
                            evento = None
                        if isinstance(evento, dict):
                            if evento.get("evento") == "trovato":
                                esito.trovati.append(evento.get("dettaglio"))
                            if "posizione" in evento:
                                esito.posizione = evento["posizione"]
                            if "esaminati" in evento:
                                esito.esaminati = evento["esaminati"]
                        if secondi_massimi and time.time() - avvio > secondi_massimi:
                            esito.interrotta = True
                            termina()
                            break
                    proc.wait(timeout=60)
                except KeyboardInterrupt:
                    esito.interrotta = True
                    termina()
                    proc.wait(timeout=60)
                finally:
                    try:
                        signal.signal(signal.SIGTERM, originale)
                    except ValueError:
                        pass

            esito.codice_uscita = proc.returncode
            esito.secondi = time.time() - avvio

        # il checkpoint scritto dal programma diventa quello da cui si riparte
        if stato_nuovo.is_file():
            shutil.move(str(stato_nuovo), str(self.file_checkpoint))
        if self.file_checkpoint.is_file():
            try:
                dati = json.loads(self.file_checkpoint.read_text(encoding="utf-8"))
                esito.posizione = dati.get("posizione", esito.posizione)
                esito.esaminati = dati.get("esaminati", esito.esaminati)
                for t in dati.get("trovati", []):
                    if t not in esito.trovati:
                        esito.trovati.append(t)
            except Exception as e:
                esito.errore = f"checkpoint illeggibile: {e}"

        esito.conclusa = (esito.codice_uscita == 0 and not esito.interrotta)
        self.file_esito.write_text(esito.to_json(), encoding="utf-8")
        return esito
