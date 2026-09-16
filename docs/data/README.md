# Raw data

Every number quoted in the documentation comes from one of these files, so that it
can be checked rather than taken on trust.

| file | what it is |
|---|---|
| `calibration_full.json`, `calibration_outcome.json`, `calibration_run1.txt`, `calibration_run2.txt` | the calibration on 11 post-cutoff problems |
| `calibration_selection.json` | how those 11 were chosen, with dates and memorisation risk |
| `archive_proofs_main13.json`, `archive_proofs_test_tier.json`, `verify_main_13.txt`, `verify_bench_v1_23.txt` | verifying the archive's own proofs: the precondition for using a problem in the calibration |
| `round0.json/txt`, `round0b.*`, `round0c.*`, `variantB*.json`, `variantC.json` | the three rounds on open problems and the instruction experiments |
| `probe_lean.json` | the automatic probe on 30 open statements |
| `targets.json`, `batch.json` | target selection |
| `fable_trial.json` | the single run with Fable 5.1 |
| `measurements.md` | the register of every measurement, with the provenance of each number |
| `searches/` | the counterexample searches: one report each, and the raw result |

**A note on language.** The `.txt` files are the raw logs of runs made in September
2026, when the tools still printed in Italian. They are kept exactly as they were
produced: rewriting a log after the fact would make it evidence of nothing. The
numbers in them are the numbers quoted in the documentation.
