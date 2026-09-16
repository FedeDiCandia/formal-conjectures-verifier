# Research data

The inputs and outputs of the searches and of the selection work. Everything here is
either downloaded unmodified from a public source or produced by the programs in this
repository.

| file or directory | what it is |
|---|---|
| `formalisation_candidates.json` | the 1209 candidates for formalising a known proof, with the score and the reasons for it |
| `formalisations_check_*.json`, `formalisations_step0_*.json` | step 0: has someone already formalised this, elsewhere? |
| `formalisations_batch20.json`, `formalisations_relaunch*.json` | the batches actually attempted |
| `bounds_cwc.json`, `bounds_general.json` | Brouwer's tables turned into JSON, with attributions |
| `reproduction.json` | verifying 361 published record codes |
| `phase1_match.json`, `phase3_*.json`, `ilp_cells.json`, `km_groups.json` | the coding-theory searches |
| `a105020_*.json` | the computational checks behind the A105020 note |
| `oeis/`, `oeis-2026-09-12/` | OEIS entries, downloaded unmodified (CC BY-SA 4.0, see NOTICE) |
| `codes/`, `Andw.html`, `binary-1.html` | Brouwer's pages and explicit codes. **Not versioned**: they carry no licence. `search/reproduce.py` downloads them when they are missing |

**A note on language.** The recorded verifier outputs (`*_verification_*.json`) keep the
`detail` strings exactly as the tools printed them in September 2026, when they printed
in Italian. They are evidence of a run: rewriting them afterwards would make them
evidence of nothing. Everything the programs print today is in English.
