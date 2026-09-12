"""
Dimostrazioni in linguaggio naturale, e un revisore severo che le smonta.

PERCHÉ
------
Tre giri sui problemi aperti hanno dato zero, e la ragione misurata è che
l'agente **non consegna candidati**: calcola, capisce dov'è la difficoltà, e si
ferma. Resta però una domanda aperta che quei giri non separano: il collo di
bottiglia è **Lean** o è la **matematica**?

Questo esperimento la separa. Si chiede una dimostrazione in linguaggio naturale,
senza Lean e senza strumenti, e poi si fa a pezzi da un revisore severo. Se
qualcosa sopravvive, il collo di bottiglia era Lean e la formalizzazione diventa
il passo successivo. Se non sopravvive niente, il collo di bottiglia è la
matematica, e nessun budget lo sposta.

COME
----
Due chiamate per problema, nessuno strumento:

  1. **autore** — dimostra o confuta, in italiano o inglese, e dichiara
     esplicitamente la propria fiducia e i punti debolial del ragionamento;
  2. **revisore** — legge senza fiducia, cerca l'errore, e dà un verdetto fra
     `REGGE`, `LACUNA`, `SBAGLIATO`, `CIRCOLARE`, `NON PERTINENTE`.

Il revisore non vede il problema come «da approvare»: il suo compito è trovare il
punto che non torna. È il ruolo in cui i modelli sono più affidabili, e la
letteratura sul tema dice che un revisore adversariale trova errori che l'autore
non vede.

Nessun uso di `lean_check`: qui non si verifica niente. Quello che esce da qui è
**materiale da leggere**, non un risultato.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
sys.path.insert(0, str(RADICE / "agent"))

import anthropic   # noqa: E402
import config as config_verificatore   # noqa: E402
from agente import carica_env          # noqa: E402
from costi import Budget, LimiteSpesaSuperato   # noqa: E402
from index import ProblemIndex         # noqa: E402

AUTORE = """You are a research mathematician. You will be given one open problem, \
stated in Lean 4 and in English.

Your task: **prove it or disprove it, in natural language.** No Lean, no code, no \
tools — just mathematics, written the way you would write it for a colleague who \
will check every step.

Rules that matter:

- If you see a proof, give it in full. Do not sketch: a sketch cannot be checked.
- If you see a counterexample, give the object explicitly and verify the required \
properties by hand.
- If you can only prove a special case or a weaker statement, do that and say \
exactly what you proved and what you did not.
- **Never** present a heuristic, a plausibility argument, or a numerical check as \
a proof. Saying "this is what I could not do" is worth more than a gap dressed up \
as an argument.

End your answer with exactly this block, filled in:

    CONFIDENCE: <one of: PROOF / PROOF-WITH-GAP / PARTIAL / NO-PROOF>
    WEAKEST STEP: <the step most likely to be wrong, in one sentence>
    WHAT WOULD FALSIFY IT: <what a reader should check first>

Be honest in that block. It is the part that will be read first."""

REVISORE = """You are a referee for a mathematics journal, and you are known for \
rejecting papers that other referees accept.

You will be given an open problem and a claimed proof or disproof. **Your job is \
to find what is wrong with it**, not to judge whether it is interesting. Assume \
the author is competent and still wrong: the interesting errors are the ones that \
look right.

Check, in this order:

1. **Does it prove the stated theorem?** Compare the Lean statement with what the \
author actually proved: a quantifier moved, a hypothesis added, a special case \
silently assumed — these are the usual failures.
2. **Is any step circular?** Does it use the conjecture, or a known-equivalent \
form of it, to prove itself?
3. **Is any step a heuristic in disguise?** "For large n this behaves like…", \
"the probability that…", "one expects…" are not steps.
4. **Is every existence claim constructive or justified?** "There must exist…" \
without a reason is a gap.
5. **Are the computations right?** Recompute the small cases yourself.

Then give exactly this block:

    VERDICT: <one of: HOLDS / GAP / WRONG / CIRCULAR / IRRELEVANT>
    THE PROBLEM: <if not HOLDS, the single most serious defect, precisely located>
    SALVAGEABLE: <what part, if any, is a genuine result>

`HOLDS` means: you tried to break it and could not. Use it sparingly — and if you \
do use it, name the step you attacked hardest."""


def messaggio_autore(p, indice) -> str:
    """Il problema, con TUTTE le definizioni che gli servono.

    Il solo enunciato non basta: `a n` o `IsPrimitiveTerm n` non si possono
    dimostrare se non si sa come sono definiti. Si manda lo stesso testo che
    riceve l'agente — il file dell'archivio con le dimostrazioni nascoste — che
    contiene le definizioni, i termini di prova dei primi valori, e il commento
    della fonte.
    """
    from nascondi import file_senza_dimostrazioni
    testo = file_senza_dimostrazioni(p, indice)
    return (f"# The problem\n\n"
            f"**Name in the archive:** `{p.theorem}`\n\n"
            f"**Statement, as elaborated by Lean:**\n\n```\n{p.statement}\n```\n\n"
            f"**Statement in English, from the archive:**\n\n{p.docstring or '(none)'}\n\n"
            f"**The whole archive file, with every proof replaced by `sorry`** — the "
            f"definitions you need are in here, and so are the verified values of "
            f"the first few terms:\n\n```lean\n{testo[:8000]}\n```\n\n"
            f"The archive marks this problem as open. Prove it or disprove it.")


def messaggio_revisore(p, prova: str) -> str:
    return (f"# The problem\n\n**Lean statement:**\n\n```\n{p.statement}\n```\n\n"
            f"**In English:** {p.docstring or '(none)'}\n\n"
            f"# The claimed proof\n\n{prova}\n\n"
            f"Now referee it.")


def una_chiamata(client, modello, sistema, testo, budget, tetto, effort,
                 max_tokens=16_000):
    conteggio = client.messages.count_tokens(
        model=modello, system=[{"type": "text", "text": sistema}],
        messages=[{"role": "user", "content": testo}])
    disponibile = budget.max_tokens_sostenibile(conteggio.input_tokens, max_tokens,
                                                residuo=tetto)
    if disponibile < 2_000:
        raise LimiteSpesaSuperato(
            f"budget insufficiente: {conteggio.input_tokens:,} token in ingresso, "
            f"spazio per la risposta {disponibile:,}")
    with client.messages.stream(
            model=modello, max_tokens=disponibile,
            system=[{"type": "text", "text": sistema}],
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": effort},
            messages=[{"role": "user", "content": testo}]) as flusso:
        risposta = flusso.get_final_message()
    budget.registra(risposta.usage, "informale")
    testo_uscita = "\n".join(b.text for b in risposta.content
                             if b.type == "text").strip()
    if not testo_uscita:
        # MISURATO l'11 settembre 2026: con effort `high` su questi problemi il
        # modello ha speso 32.000 token di ragionamento senza scrivere una riga
        # di risposta, per $0,81 di niente, e il revisore ha poi recensito una
        # pagina bianca. Pagare e non ricevere nulla non e' un esito ammissibile:
        # qui si ferma, con il motivo esatto.
        raise LimiteSpesaSuperato(
            f"risposta vuota: stop_reason={risposta.stop_reason}, "
            f"{risposta.usage.output_tokens:,} token in uscita di cui "
            f"{getattr(risposta.usage.output_tokens_details, 'thinking_tokens', '?')} "
            f"di ragionamento. Il tetto di max_tokens era {disponibile:,}: "
            f"serve piu' spazio oppure un effort piu' basso.")
    return testo_uscita, risposta.usage


def estrai(blocco: str, chiave: str) -> str:
    for riga in blocco.split("\n"):
        if riga.strip().upper().startswith(chiave.upper()):
            return riga.split(":", 1)[1].strip()[:200]
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("problemi", nargs="+")
    ap.add_argument("--modello", default="claude-opus-5")
    # MISURATO l'11 settembre 2026 sullo stesso problema, con lo stesso ingresso:
    #   effort high,   tetto 32k -> 32.000 token, TUTTI di ragionamento, zero righe
    #   effort medium, tetto 24k -> 24.000 token, TUTTI di ragionamento, zero righe
    #   effort low,    tetto 24k -> 20.402 token (16.353 di ragionamento),
    #                               7.066 caratteri di matematica vera, end_turn
    # A effort alto il modello esaurisce lo spazio pensando e non conclude. A
    # effort basso conclude, e conclude bene: sul primo problema ha dimostrato che
    # la congettura implica un caso del problema del totiente di Lehmer, che e'
    # aperto, piu' cinque risultati parziali rigorosi. Il valore predefinito e'
    # quindi `low`, e non e' un risparmio: e' l'unico che funziona.
    ap.add_argument("--effort", default="low")
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--tetto-problema", type=float, default=1.20)
    ap.add_argument("--rapporto", default=str(RADICE / "runs" / "informale.json"))
    ap.add_argument("--registro", default=None)
    args = ap.parse_args()

    percorso_registro = Path(args.registro) if args.registro else (
        RADICE / "runs" / "lavori" / f"informale-{time.strftime('%Y%m%d-%H%M%S')}.log")
    percorso_registro.parent.mkdir(parents=True, exist_ok=True)
    import agente
    sys.stdout = agente._Doppio(sys.stdout, percorso_registro)
    print(f"Registro: {percorso_registro}")

    carica_env()
    client = anthropic.Anthropic()
    idx = ProblemIndex.load()
    budget = Budget(limite_dollari=args.budget, modello=args.modello)
    print(f"Modello {args.modello}, effort {args.effort}, budget ${args.budget:.2f}, "
          f"tetto ${args.tetto_problema:.2f} per problema")
    print("Nessuno strumento, nessun Lean: solo matematica in linguaggio naturale.\n")

    esiti = []
    for i, nome in enumerate(args.problemi, 1):
        p = idx.get(nome)
        print(f"\n{'='*78}\n[{i}/{len(args.problemi)}] {nome}\n{'='*78}")
        speso_prima = budget.speso
        voce = {"problema": nome, "enunciato": p.statement[:300]}
        try:
            prova, _ = una_chiamata(client, args.modello, AUTORE,
                                    messaggio_autore(p, idx), budget,
                                    args.tetto_problema * 0.7, args.effort)
            voce["prova"] = prova
            voce["fiducia"] = estrai(prova, "CONFIDENCE")
            voce["punto_debole"] = estrai(prova, "WEAKEST STEP")
            print(f"  autore:   {voce['fiducia'] or '(non dichiarata)'}")
            print(f"            punto debole: {voce['punto_debole'][:100]}")

            # Il revisore esiste per rompere una dimostrazione rivendicata. Se
            # l'autore dichiara di non averne una, non c'e' niente da arbitrare e
            # la seconda chiamata e' denaro buttato: sui problemi di questo
            # insieme la maggioranza degli esiti e' PARTIAL o NO-PROOF, quindi
            # questa condizione e' la differenza fra dodici problemi e venti.
            fiducia = voce["fiducia"].upper()
            if fiducia.startswith(("PARTIAL", "NO-PROOF", "NO PROOF")):
                voce["recensione"] = None
                voce["verdetto"] = "(non arbitrato: l'autore non rivendica una prova)"
                voce["difetto"] = ""
                print("  revisore: salta, l'autore non rivendica una prova")
            else:
                recensione, _ = una_chiamata(
                    client, args.modello, REVISORE, messaggio_revisore(p, prova),
                    budget, args.tetto_problema - (budget.speso - speso_prima),
                    args.effort)
                voce["recensione"] = recensione
                voce["verdetto"] = estrai(recensione, "VERDICT")
                voce["difetto"] = estrai(recensione, "THE PROBLEM")
                print(f"  revisore: {voce['verdetto'] or '(non dichiarato)'}")
                print(f"            difetto: {voce['difetto'][:100]}")
        except LimiteSpesaSuperato as e:
            voce["errore"] = str(e)
            print(f"  !! {e}")
            esiti.append(voce)
            break
        except anthropic.APIError as e:
            voce["errore"] = f"API: {e}"
            print(f"  !! errore dall'API: {e}")
            esiti.append(voce)
            if "credit" in str(e).lower():
                print("  credito esaurito: mi fermo.")
                break
            continue
        voce["costo"] = round(budget.speso - speso_prima, 4)
        print(f"  costo: ${voce['costo']:.4f}   (totale ${budget.speso:.4f})")
        esiti.append(voce)
        # Il rapporto si scrive a OGNI problema, non alla fine. Misurato il 12
        # settembre 2026: un errore mio (`recensione` non definita quando il
        # revisore viene saltato) ha fatto morire il giro dopo il primo problema, e
        # il testo del primo -- gia' pagato -- e' andato perso perche' il file
        # veniva scritto solo in fondo. Un lavoro che paga deve salvare mentre va.
        Path(args.rapporto).write_text(json.dumps(
            {"modello": args.modello, "effort": args.effort,
             "speso": budget.speso, "tetto_problema": args.tetto_problema,
             "in_corso": True, "esiti": esiti},
            ensure_ascii=False, indent=1), encoding="utf-8")

    sopravvissuti = [v for v in esiti if v.get("verdetto", "").upper().startswith("HOLDS")]
    print(f"\n{'='*78}\nRESOCONTO\n{'='*78}")
    for v in esiti:
        print(f"  {v['problema'][:46]:46} autore {v.get('fiducia','-')[:14]:14} "
              f"revisore {v.get('verdetto','-')[:12]:12} ${v.get('costo',0):.4f}")
    print(f"\n  sopravvissuti alla revisione: {len(sopravvissuti)} su {len(esiti)}")
    print(f"  spesa totale: ${budget.speso:.4f} su ${args.budget:.2f}")
    Path(args.rapporto).write_text(json.dumps(
        {"modello": args.modello, "effort": args.effort, "speso": budget.speso,
         "tetto_problema": args.tetto_problema, "esiti": esiti},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  rapporto in {args.rapporto}")
    if sopravvissuti:
        print("\n  ATTENZIONE: quello che sopravvive alla revisione NON e' un")
        print("  risultato. E' materiale da leggere, e il passo successivo e' il")
        print("  protocollo di docs/04 piu' la formalizzazione in Lean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
