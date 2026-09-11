"""
Strumento di ESPLORAZIONE: compila un file Lean e restituisce tutti i messaggi.

PERCHE' E' SEPARATO DA verify.py
--------------------------------
`verify.py` risponde a una sola domanda: "questa e' una dimostrazione valida del
problema?". Per farlo compila, esporta, confronta gli enunciati, controlla gli
assiomi e riesegue tutto nel kernel. Costa una trentina di secondi ed e' la cosa
giusta da fare quando si consegna una dimostrazione.

Ma il primo collaudo con l'agente ha mostrato che **la maggior parte delle
chiamate non erano consegne**: erano tentativi di capire come Mathlib definisce
qualcosa. Nove verifiche su nove, in quel caso. Usare il giudice per ispezionare
una definizione e' come chiedere una sentenza per sapere che ore sono: lento,
costoso, e il verdetto ("rifiutato: il teorema non c'e'") non e' l'informazione
cercata.

Questo modulo fa solo la parte utile a esplorare:

  * esegue `lake env lean` sul file, senza comparator, senza esportazione,
    senza confronto e senza riesecuzione nel kernel;
  * restituisce **tutti** i messaggi, non troncati: l'output di `#print`,
    `#check`, `#eval`-libere come `exact?`, e gli errori completi con lo stato
    degli obiettivi;
  * NON e' una verifica e non va contata come tale. Un file che "passa" qui non
    ha dimostrato niente.

Misurato: 8,0 secondi contro i 32,9 di una verifica completa, e l'output e' piu'
pulito perche' `lean` invocato direttamente non applica i linter di stile che
`lake build` applica alla libreria dell'archivio.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import guard
import impronta as modulo_impronta
import sandbox


@dataclass
class Esplorazione:
    """Il risultato di una compilazione di prova."""
    ok: bool                 # il file compila senza errori
    messaggi: str            # tutti i messaggi di Lean, non troncati
    secondi: float
    isolato: bool            # se e' girata dentro la sandbox
    troncato: bool = False
    #: violazioni del controllo sintattico: se ce ne sono, non si compila niente
    rifiutato_dal_guard: list = None

    def render(self) -> str:
        testa = (f"{'compila senza errori' if self.ok else 'con errori'}  "
                 f"({self.secondi:.1f}s"
                 f"{'' if self.isolato else ', SENZA isolamento'})")
        return f"{testa}\n\n{self.messaggi}" if self.messaggi else testa


#: Limite generoso. Serve solo a non far esplodere il contesto se qualcuno
#: stampa mezzo Mathlib; gli errori di Lean stanno ampiamente sotto.
MAX_CARATTERI = 40_000


def esplora(codice: str, *, timeout: int = 240, slot: int = 0) -> Esplorazione:
    """Compila `codice` e riporta tutto quello che Lean ha da dire."""
    problemi = config.check_installation()
    if problemi:
        return Esplorazione(False, "Ambiente non pronto:\n  - " + "\n  - ".join(problemi),
                            0.0, False)

    # Il controllo sintattico vale anche qui: un file di ispezione viene
    # compilato come qualunque altro, quindi puo' eseguire codice allo stesso
    # modo. L'unica regola allentata sono gli import (vedi guard.check_source).
    rapporto = guard.check_source(codice, esplorazione=True)
    if not rapporto.ok:
        return Esplorazione(
            False,
            "Il file contiene costrutti vietati e non e' stato compilato:\n\n"
            + "\n".join(str(f) for f in rapporto.findings),
            0.0, False, rifiutato_dal_guard=[f.rule for f in rapporto.findings])

    cartella = config.ARCHIVE / config.SANDBOX_SUBDIR
    cartella.mkdir(parents=True, exist_ok=True)
    percorso = cartella / f"E{slot}.lean"
    percorso.write_text(codice, encoding="utf-8")
    relativo = str(percorso.relative_to(config.ARCHIVE))

    avvio = time.time()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            profilo = None
            if config.USA_SANDBOX and sandbox.disponibile():
                for d in sandbox.cartelle_scrivibili(
                        config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir):
                    d.mkdir(parents=True, exist_ok=True)
                profilo = sandbox.scrivi_profilo(
                    tmp_dir / "esplora.sb",
                    sandbox.cartelle_scrivibili(config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir),
                    config.ROOT)

            impronta_prima = None
            if config.CONTROLLA_IMPRONTA:
                impronta_prima = modulo_impronta.calcola(
                    config.ARCHIVE, escludi=Path(config.SANDBOX_SUBDIR).name)

            ambiente = config.lean_env()
            ambiente["TMPDIR"] = str(tmp_dir)
            comando = [str(config.ELAN_BIN / "lake"), "env", "lean", relativo]
            if profilo is not None:
                comando = sandbox.avvolgi(comando, profilo)

            proc = subprocess.Popen(
                comando, cwd=str(config.ARCHIVE), env=ambiente,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, start_new_session=True)
            try:
                uscita, _ = proc.communicate(timeout=timeout)
                codice_uscita = proc.returncode
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                uscita = (f"TEMPO SCADUTO: la compilazione ha superato {timeout} secondi. "
                          f"Probabilmente una tattica non termina, o un `#reduce` su un "
                          f"termine enorme.")
                codice_uscita = -1

            if impronta_prima is not None:
                differenze = modulo_impronta.confronta(
                    impronta_prima,
                    modulo_impronta.calcola(config.ARCHIVE,
                                            escludi=Path(config.SANDBOX_SUBDIR).name))
                if differenze:
                    uscita = ("ATTENZIONE: compilare questo file ha MODIFICATO l'archivio.\n"
                              + "\n".join("  - " + d for d in differenze)
                              + "\n\n" + uscita)
                    codice_uscita = -2
    finally:
        percorso.unlink(missing_ok=True)

    durata = time.time() - avvio
    troncato = len(uscita) > MAX_CARATTERI
    if troncato:
        uscita = uscita[:MAX_CARATTERI] + (
            f"\n\n... [output troncato a {MAX_CARATTERI} caratteri]")
    return Esplorazione(ok=(codice_uscita == 0), messaggi=uscita.strip(),
                        secondi=durata, isolato=(profilo is not None), troncato=troncato)


if __name__ == "__main__":
    testo = sys.stdin.read() if len(sys.argv) < 2 else Path(sys.argv[1]).read_text(encoding="utf-8")
    print(esplora(testo).render())
