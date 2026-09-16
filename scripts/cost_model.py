"""
The cost model, and the projection onto the open problems.

Every number printed carries a label:

  MEASURED   it comes from a run recorded in a file in this repository.
  ESTIMATED  it is a hypothesis. The reasoning that supports it is always beside it.

The model uses no external libraries: the confidence interval is Clopper-Pearson's,
computed by bisection on the exact binomial sum, so scipy is not needed and the
arithmetic is reproducible by anyone who reads the code.

Usage:  python3 scripts/cost_model.py > runs/cost_model.txt
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
from index import ProblemIndex   # noqa: E402

LEVELS = ("easy", "medium", "hard")
SPEND_LEVELS = (50, 100, 200, 500, 1000, 5000)


# ---------------------------------------------------------------- statistica
def _binom_upper_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p). An exact sum, no libraries."""
    return sum(math.comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k, n + 1))


def _binom_lower_tail(k: int, n: int, p: float) -> float:
    """P(X <= k)."""
    return sum(math.comb(n, i) * p**i * (1 - p)**(n - i) for i in range(0, k + 1))


def _bisection(f, target: float, lo: float, hi: float) -> float:
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, confidence_level: float = 0.90) -> tuple[float, float]:
    """The Clopper-Pearson interval for a proportion k/n.

    It is the interval that assumes nothing about the shape of the distribution: with
    small numbers it stays wide, and it is right that it should.
    """
    alpha = 1 - confidence_level
    low = 0.0 if k == 0 else _bisection(
        lambda p: _binom_upper_tail(k, n, p), alpha / 2, 0.0, 1.0)
    high = 1.0 if k == n else _bisection(
        lambda p: 1 - _binom_lower_tail(k, n, p), 1 - alpha / 2, 0.0, 1.0)
    return low, high


# ---------------------------------------------------------------- data
def load() -> dict:
    data = {}
    data["cal"] = json.loads(
        (ROOT / "docs/data/calibration_full.json").read_text(encoding="utf-8"))

    idx = {}
    for name, perc in (("bench-v1", "verifier/problem_index.json"),
                       ("main", "verifier/problem_index_main.json")):
        i = ProblemIndex.load(ROOT / perc)
        open_problems = i.find(category="research open")
        ap_ver = [p for p in open_problems if not p.statement_has_sorry]
        ris = i.find(category="research solved")
        idx[name] = {
            "theorems": len(i.problems),
            "open_problems": len(open_problems),
            "open_verifiable": len(ap_ver),
            "open_with_non_prop_hole": len(open_problems) - len(ap_ver),
            "open_refutable": len([p for p in open_problems
                                       if p.answer_placeholder_in_source
                                       and not p.statement_has_sorry]),
            "open_variants": len([p for p in ap_ver if ".variants." in p.theorem]),
            "solved": len(ris),
            "solved_with_clean_proof": len([p for p in ris if p.archive_proof_is_clean]),
            "solved_without_proof": len([p for p in ris if not p.proof_is_complete
                                        and not p.statement_has_sorry]),
            "complete_proofs": len([p for p in i.problems if p.proof_is_complete]),
            "clean_proofs": len([p for p in i.problems if p.archive_proof_is_clean]),
        }
    data["index"] = idx

    # prefer the versioned copy in docs/data, so the report regenerates even on a
    # machine where runs/ does not exist (runs/ is not under git)
    probe = next((p for p in (ROOT / "docs/data/probe_lean.json",
                              ROOT / "runs/hunt/probe_lean.json") if p.is_file()),
                 None)
    data["probe"] = json.loads(probe.read_text(encoding="utf-8")) if probe else None

    caccia = []
    for folder in sorted((ROOT / "runs/hunt").glob("*/")):
        f = folder / "state.json"
        g = folder / "result.json"
        entry = {"name": folder.name}
        for key, path in (("state", f), ("result", g)):
            if path.is_file():
                entry[key] = json.loads(path.read_text(encoding="utf-8"))
        if len(entry) > 1:
            caccia.append(entry)
    data["hunt"] = caccia
    return data


# ---------------------------------------------------------------- model
def per_level(problems: list[dict]) -> dict:
    outside = {}
    for lvl in LEVELS:
        group = [p for p in problems if p["level"] == lvl]
        if not group:
            continue
        solved = [p for p in group if p["solved"]]
        failed = [p for p in group if not p["solved"]]
        low, high = clopper_pearson(len(solved), len(group))
        outside[lvl] = {
            "n": len(group), "solved": len(solved),
            "rate": len(solved) / len(group),
            "interval": (low, high),
            "success_costs": [p["cost"] for p in solved],
            "failure_costs": [p["cost"] for p in failed],
            "success_iterations": [p["iterations"] for p in solved],
            "seconds": [p["seconds"] for p in group],
        }
    return outside


def cost_per_success(p: float, c_success: float, c_failure: float) -> float:
    """Expected cost of obtaining ONE success, with independent attempts."""
    if p <= 0:
        return float("inf")
    return (c_success * p + c_failure * (1 - p)) / p


def projection_table(name: str, c_attempt: float, p: float) -> list[tuple]:
    lines = []
    for b in SPEND_LEVELS:
        n = b / c_attempt
        lines.append((b, n, n * p))
    return lines


def fmt(x: float) -> str:
    if x == float("inf"):
        return "infinito"
    if x == 0:
        return "0"
    if x >= 1000:
        return f"{x:,.0f}".replace(",", " ")
    if x >= 10:
        return f"{x:.0f}"
    if x >= 1:
        return f"{x:.1f}"
    return f"{x:.3f}"


# ---------------------------------------------------------------- scenari
#
# These are the model's ONLY invented numbers. Each carries its reasoning, and the
# reasoning says which measurement it rests on.

SCENARIOS = {
    "A": {
        "name": "dimostrazioni Lean dirette su enunciati open_problems",
        "optimistic": (0.02,
            "the automatic probe closed none of the 30 open statements it tried "
            "(240 attempts): the measured 90% upper bound is 9.5%. I take about a "
            "fifth of that ceiling, because the probe tries tactics whereas the agent "
            "reasons — so it can do better — but 9.5% is the ceiling of a sample of "
            "30, not an estimate"),
        "realistic": (0.003,
            "one success every ~300 attempts: the calibration measures 5/7 on "
            "variants ALREADY proved in the archive (proofs of 10-34 lines), but no "
            "open problem has a known short proof, by definition of open"),
        "pessimistic": (0.0002,
            "one success every 5000: the archive is curated by DeepMind to collect "
            "problems on which the experts have stopped"),
    },
    "B": {
        "name": "hunting counterexamples with local computation",
        "optimistic": (0.05,
            "a minority of conjectures have low verified bounds (for Selfridge's "
            "conjecture the literature stops at k~29): on those, local computation "
            "really does go past the known"),
        "realistic": (0.01,
            "measured in this project: 0 findings in 3 searches and ~2 CPU-hours; "
            "the Euclid-number search passed 2.5 million primes with nothing"),
        "pessimistic": (0.001,
            "the published bounds are nearly always out of reach: for Erdos 366 the "
            "verification reaches 10^22"),
    },
    "C": {
        "name": "mixed strategy: a cheap sieve, then a full attempt",
        "optimistic": (None, "derivato da A e B"),
        "realistic": (None, "derivato da A e B"),
        "pessimistic": (None, "derivato da A e B"),
    },
}


# Parameters of the mixed strategy. Three numbers, declared here.
DIVE_SHARE = 0.10       # ESTIMATED: of 10 problems sieved, 1 deserves a full attempt
AMPLIFICATION = {"optimistic": 3.0, "realistic": 2.0, "pessimistic": 1.0}
FIRST_SHOT_SHARE = 0.22   # MEASURED: 2 of the 9 successes arrived on the first
                           # iteration (Wilson, ClaudesCycles)

# Strategia B: how_many targets esistono davvero.
N_SELECTED_HUNT = 30          # MISURATO: runs/hunt/selection.json
REACHABLE_FRONTIER_FRACTION = 0.50   # STIMATO su 2 letterature su 4 controllate

# What the searches that were run did. The findings are ZERO in all three: the
# `found` entry of erdos396 holds COMPUTED values (the least n for each k), not
# counterexamples, and has to be read that way.
HUNT = {
    "euclide_squarefree": (
        "a prime p with p^2 dividing a Euclid number",
        "conclusive: a single finding would refute the conjecture", 0),
    "erdos409_sigma": (
        "orbits of n -> sigma(n)-1 that never hit a prime",
        "finds suspects to examine by hand, not refutations", 0),
    "erdos396_binomiale": (
        "the least n with descFactorial(n,k+1) dividing centralBinom(n)",
        "gathers evidence: the form 'for every k there exists n' cannot be refuted "
        "by computation", 0),
}


def report_text(data: dict) -> str:
    r: list[str] = []
    def p(s: str = "") -> None:
        r.append(s)

    cal = data["cal"]
    problems = cal["problems"]
    idx = data["index"]
    lvl = per_level(problems)

    solved = [x for x in problems if x["solved"]]
    failed = [x for x in problems if not x["solved"]]
    c_succ = st.mean(x["cost"] for x in solved)
    c_fall = st.mean(x["cost"] for x in failed)
    c_it1 = st.median(x["first_iteration_cost"] for x in problems)

    p("# The cost model, and a projection onto the open problems")
    p()
    p(f"Generated by `scripts/cost_model.py`. Model **{cal['model']}**, "
      f"effort **{cal['effort']}**, snapshot `{cal['snapshot']}`.")
    p()

    # ---------------------------------------------------------------- 1
    p("## 1. What was measured")
    p()
    p(f"**MEASURED** — {len(problems)} problems attempted, {len(solved)} solved, "
      f"total spend ${cal['total_spend']:.4f}. All of them entered the archive after "
      f"the declared training cutoff ({cal['training_cutoff']}), all with the "
      f"archive's own proof accepted by the verifier, all with that proof hidden from "
      f"the agent.")
    p()
    p("| level | lines di trial | result | iter. | espl. | checks | seconds | cost |")
    p("|---|---|---|---|---|---|---|---|")
    for x in problems:
        p(f"| {x['level']} | {x['proof_lines']} | "
          f"{'**solved**' if x['solved'] else 'not solved'} | "
          f"{x['iterations']} | {x['explorations']} | {x['verifications']} | "
          f"{x['seconds']} | ${x['cost']:.4f} |")
    p()

    # ---------------------------------------------------------------- 2
    p("## 2. The model, level by level")
    p()
    p("Each success rate comes with a 90% Clopper-Pearson interval: with four or five "
      "problems per level the interval is enormous, and stating it is the only honest "
      "way to give the number.")
    p()
    p("| level | n | solved | rate | 90% interval | mean cost when solved | cost when failed |")
    p("|---|---|---|---|---|---|---|")
    for name, v in lvl.items():
        cs = f"${st.mean(v['success_costs']):.4f}" if v["success_costs"] else "—"
        cf = (f"${st.mean(v['failure_costs']):.4f}" if v["failure_costs"] else "—")
        p(f"| {name} | {v['n']} | {v['solved']} | {v['rate']:.0%} | "
          f"{v['interval'][0]:.0%} – {v['interval'][1]:.0%} | {cs} | {cf} |")
    tot_b, tot_a = clopper_pearson(len(solved), len(problems))
    p(f"| **total** | {len(problems)} | {len(solved)} | "
      f"{len(solved)/len(problems):.0%} | {tot_b:.0%} – {tot_a:.0%} | "
      f"${c_succ:.4f} | ${c_fall:.4f} |")
    p()
    p("**MEASURED** — the four `easy` entries are problems of "
      "categoria `test`, cioe' controlli di sanita' scritti dagli autori "
      "the archive: 4 out of 4. The seven `medium` and `hard` entries are variants "
      "di congetture vere e proprie, di categoria `research solved`: 5 su 7. "
      "The number to remember is **5 out of 7**, not 9 out of 11.")
    p()
    p(f"**MEASURED** — mean cost of a success ${c_succ:.4f}; mean cost of a failure "
      f"${c_fall:.4f}. A failure costs {c_fall/c_succ:.0f} times a success, because a "
      f"failure consumes the whole per-problem cap while a success stops as soon as "
      f"dimostrazione passa.")
    p()
    p(f"**MEASURED** — cost of the FIRST iteration, median over {len(problems)} "
      f"problems: ${c_it1:.4f}. Two of the nine successes arrived on the first "
      f"iteration. This is the price of a single shot, and it is the basis of "
      f"strategia mista del punto 4.")
    p()
    lean_hours = sum(x["lean_seconds"] for x in problems) / 3600
    total_hours = sum(x["seconds"] for x in problems) / 3600
    p(f"**MEASURED** — wall-clock time: {total_hours:.2f} hours in all, of which "
      f"{lean_hours:.2f} hours of Lean locally ({100*lean_hours/total_hours:.0f}%). "
      f"The bottleneck is not the API: it is the verifier.")
    p()
    p("### Cost per problem solved")
    p()
    p("Formula: (cost se solved x p + cost se failed x (1-p)) / p, cioe' quanto "
      "it costs on average to reach ONE success, retrying on different problems.")
    p()
    p("| level | p | cost per success | with p at the bottom of the interval | at the top |")
    p("|---|---|---|---|---|")
    for name, v in lvl.items():
        cs = st.mean(v["success_costs"]) if v["success_costs"] else c_succ
        cf = st.mean(v["failure_costs"]) if v["failure_costs"] else c_fall
        a = cost_per_success(v["rate"], cs, cf)
        b = cost_per_success(v["interval"][0], cs, cf)
        c = cost_per_success(v["interval"][1], cs, cf)
        p(f"| {name} | {v['rate']:.0%} | ${fmt(a)} | ${fmt(b)} | ${fmt(c)} |")
    p()
    return r

def report_part_two(data: dict, r: list[str]) -> list[str]:
    def p(s: str = "") -> None:
        r.append(s)

    cal = data["cal"]
    problems = cal["problems"]
    idx = data["index"]
    solved = [x for x in problems if x["solved"]]
    failed = [x for x in problems if not x["solved"]]
    c_succ = st.mean(x["cost"] for x in solved)
    c_fall = st.mean(x["cost"] for x in failed)
    c_it1 = st.median(x["first_iteration_cost"] for x in problems)

    # ---------------------------------------------------------------- 3
    p("## 3. How many targets there are")
    p()
    p("| | bench-v1 | main (0a8b856c) |")
    p("|---|---|---|")
    entries = [
        ("theorems indicizzati", "theorems"),
        ("`research open`", "open_problems"),
        ("open with a complete statement (verifiable)", "open_verifiable"),
        ("open with a non-propositional `answer( )` hole", "open_with_non_prop_hole"),
        ("open and attackable by refutation", "open_refutable"),
        ("open ones that are auxiliary variants", "open_variants"),
        ("`research solved`", "solved"),
        ("solved with a clean proof in the archive", "solved_with_clean_proof"),
        ("solved WITHOUT a proof in the archive", "solved_without_proof"),
    ]
    for label, key in entries:
        p(f"| {label} | {idx['bench-v1'][key]} | {idx['main'][key]} |")
    p()
    p("All **MEASURED** on the index built by Lean.")
    p()
    p("The `main` counts hold under the default semantics "
      "`google.answer = always_true`, in which `answer(sorry) ↔ P` becomes `True ↔ P` "
      "and the problem really is provable. Until this session the snapshot also "
      "declared a second library that compiled the same files with `postpone`, and the "
      "two sets of `.olean` files overwrote each other: under that semantics the same "
      "94 problems are not attackable at all. The surplus library has been disabled — "
      "see `docs/01-the-archive.md` — and the numbers above are those of the right "
      "semantics.")
    p()
    p(f"Two observations that change the strategy. First: **none** of the "
      f"{idx['main']['open_problems']} problems marcati `research open` ha one "
      f"has a complete proof in the archive — the archive is consistent with itself, "
      f"there are no 'accidentally open' problems to harvest. Second: "
      f"{idx['main']['solved_without_proof']} problems are marked `research solved` but "
      f"have no Lean proof in the archive: the mathematics is known, the formalisation "
      f"is missing. That is a third class of target, easier than the open ones and "
      f"harder than those the calibration used.")
    p()

    # ---------------------------------------------------------------- 4
    p("## 4. Proiezione sui problems open_problems")
    p()
    p("The probabilities of success on an **open** problem are not measurable: they "
      "are the three hypotheses below, and every line declares what it rests on. The "
      "arithmetic accounts for the targets being **finite** in number: once a strategy "
      "has exhausted them, extra spending buys nothing this model can evaluate.")
    p()
    n_targets = idx["main"]["open_verifiable"]
    c_a = c_fall
    c_s = c_it1
    c_b = 0.10

    p("### Cost of an attempt (the basis of the arithmetic)")
    p()
    p(f"- **A, full attempt** on an open statement: **${c_a:.2f}** — "
      f"**MEASURED**, the mean of the calibration's two failures "
      f"(${failed[0]['cost']:.4f} fermato dalle 20 iterations, "
      f"${failed[1]['cost']:.4f} stopped by the spending cap). On an open problem an "
      f"attempt nearly always ends that way.")
    p(f"- **C, single shot** (the sieve): **${c_s:.4f}** — **MEASURED**, the median "
      f"cost of the first iteration over the 11 calibration problems.")
    p(f"- **B, program di ricerca** scritto e lanciato: **${c_b:.2f}** di API "
      f"per problem — **ESTIMATED**, of the order of the measured cost of the easy "
      f"facili (media "
      f"${st.mean(x['cost'] for x in problems if x['level']=='easy'):.4f}). "
      f"Local computation costs no dollars: it costs machine-nights.")
    p()

    # ------------------------------------------------- A
    p("### Strategia A — dimostrazioni Lean dirette su enunciati open_problems")
    p()
    p(f"One attempt per problem, chosen at random among the {n_targets} verifiable "
      f"verificabili. Saturazione a **${fmt(n_targets*c_a)}**.")
    p()
    p("| spend | attempts | optimistic | realistic | pessimistic |")
    p("|---|---|---|---|---|")
    for b in SPEND_LEVELS:
        n = min(b / c_a, n_targets)
        note = " *(saturo)*" if b / c_a > n_targets else ""
        cells = [fmt(n * SCENARIOS["A"][sc][0])
                 for sc in ("optimistic", "realistic", "pessimistic")]
        p(f"| ${b} | {fmt(n)}{note} | {cells[0]} | {cells[1]} | {cells[2]} |")
    p()
    for sc in ("optimistic", "realistic", "pessimistic"):
        prob, reason = SCENARIOS["A"][sc]
        p(f"- **{sc}: p = {prob:.2%}** — STIMATO. {reason}.")
    p()

    # ------------------------------------------------- B
    eligible_total = N_SELECTED_HUNT
    reachable_share = REACHABLE_FRONTIER_FRACTION
    n_b = eligible_total * reachable_share
    p("### Strategy B — hunting counterexamples with local computation")
    p()
    p(f"Here the limit is not money: it is the number of problems on which a search "
      f"makes sense. **MEASURED**: the selection script found {eligible_total} of them "
      f"suitable for computation across the whole archive. Of the four whose "
      f"literature I checked, two have a reachable frontier "
      f"(numbers di Euclide: nessuna ricerca sistematica pubblicata; congettura di "
      f"Selfridge: verificata only fino a k circa 29) e two no (Erdos 366: "
      f"verificata fino a 10^22; Goldbach e Legendre: fino a 4x10^18). Due su "
      f"quattro, interval di Clopper-Pearson al 90% "
      f"{clopper_pearson(2,4)[0]:.0%} – {clopper_pearson(2,4)[1]:.0%}: "
      f"**ESTIMATED** {reachable_share:.0%}, so about "
      f"**{n_b:.0f} targets real_list**.")
    p()
    p(f"API cost to saturate the strategy: {n_b:.0f} x ${c_b:.2f} = "
      f"**${n_b*c_b:.2f}**. Machine time: with 8 searches in parallel, "
      f"circa {n_b/8:.0f}-{n_b/4:.0f} notti.")
    p()
    p("| spend | searches | optimistic | realistic | pessimistic |")
    p("|---|---|---|---|---|")
    for b in SPEND_LEVELS:
        n = min(b / c_b, n_b)
        note = " *(saturo)*" if b / c_b > n_b else ""
        cells = [fmt(n * SCENARIOS["B"][sc][0])
                 for sc in ("optimistic", "realistic", "pessimistic")]
        p(f"| ${b} | {fmt(n)}{note} | {cells[0]} | {cells[1]} | {cells[2]} |")
    p()
    for sc in ("optimistic", "realistic", "pessimistic"):
        prob, reason = SCENARIOS["B"][sc]
        p(f"- **{sc}: p = {prob:.2%}** per search — ESTIMATED. {reason}.")
    p()
    p("Strategy B is **saturated at under two dollars of API**. The whole spending "
      "column, from $50 to $5000, changes nothing: what is missing is not money but "
      "problems with a reachable frontier. And any finding is, by the protocol in "
      "docs/04-finding-protocol.md, more likely a faulty formalisation than a new "
      "result.")
    p()

    # ------------------------------------------------- C
    p("### Strategy C — mixed: sieve first, then targeted attempts")
    p()
    p(f"Give **a single shot** (${c_s:.4f}) to as many problems as possible, up to all "
      f"{n_targets}; with what is left, buy ${c_a:.2f} attempts, starting from the "
      f"problems where the single shot showed a sensible plan. The first "
      f"{DIVE_SHARE:.0%} of the attempts get the amplification (they are the selected "
      f"ones), the rest count as A.")
    p()
    p("| spend | sieved | attempts | optimistic | realistic | pessimistic |")
    p("|---|---|---|---|---|---|")
    for b in SPEND_LEVELS:
        n_scr = min(n_targets, b / c_it1)
        resto = max(0.0, b - n_scr * c_it1)
        n_dive = min(n_scr, resto / c_fall)
        cells = []
        for sc in ("optimistic", "realistic", "pessimistic"):
            p_a = SCENARIOS["A"][sc][0]
            m = AMPLIFICATION[sc]
            head = min(n_dive, DIVE_SHARE * n_scr)
            queue = n_dive - head
            expected = n_scr * FIRST_SHOT_SHARE * p_a + head * m * p_a + queue * p_a
            cells.append(fmt(expected))
        p(f"| ${b} | {fmt(n_scr)} | {fmt(n_dive)} | "
          f"{cells[0]} | {cells[1]} | {cells[2]} |")
    p()
    p(f"- the single shot captures **{FIRST_SHOT_SHARE:.0%}** of the successes a full "
      f"attempt would get — **MEASURED**: 2 of the 9 calibration successes arrived on "
      f"the first iteration;")
    p(f"- selected attempts are worth {AMPLIFICATION['optimistic']:.0f}x / "
      f"{AMPLIFICATION['realistic']:.0f}x / "
      f"{AMPLIFICATION['pessimistic']:.0f}x a blind attempt — **ESTIMATED**: the "
      f"single shot discards the problems on which the model has no plan at all; in "
      f"the calibration both failures had a coherent plan from the first iteration, so "
      f"the signal exists but is "
      f"imperfetto.")
    p(f"- **MEASURED** — covering all {n_targets} verifiable open problems with a "
      f"verificabili costa **${n_targets*c_s:.0f}**.")
    p()

    p("### The comparison in one line")
    p()
    p("| scenario | dollars per success, A | dollars per success, C | advantage of C |")
    p("|---|---|---|---|")
    for sc in ("optimistic", "realistic", "pessimistic"):
        p_a = SCENARIOS["A"][sc][0]
        m = AMPLIFICATION[sc]
        resa_a = p_a / c_a
        # C at break-even: sieve everything + a full attempt on the best 10%
        costo_c = n_targets * c_s + DIVE_SHARE * n_targets * c_a
        succ_c = (n_targets * FIRST_SHOT_SHARE * p_a
                  + DIVE_SHARE * n_targets * m * p_a)
        resa_c = succ_c / costo_c
        p(f"| {sc} | ${fmt(1/resa_a)} | ${fmt(1/resa_c)} | "
          f"{resa_c/resa_a:.1f}x |")
    p()
    p(f"The break-even point of strategy C — one shot at all {n_targets} open "
      f"problems, plus a full attempt on the best {DIVE_SHARE:.0%} — costs "
      f"**${n_targets*c_s + DIVE_SHARE*n_targets*c_a:.0f}**. That is the figure to "
      f"remember: it is the price of one complete pass over the archive.")
    p()
    return r

def report_part_three(data: dict, r: list[str]) -> list[str]:
    def p(s: str = "") -> None:
        r.append(s)

    idx = data["index"]
    problems = data["cal"]["problems"]
    c_fall = st.mean(x["cost"] for x in problems if not x["solved"])
    c_it1 = st.median(x["first_iteration_cost"] for x in problems)
    c_c = c_it1 + DIVE_SHARE * c_fall
    n_targets = idx["main"]["open_verifiable"]

    # ---------------------------------------------------------------- 5
    p("## 5. The local computation, measured")
    p()
    p("Strategy B is paid in machine time rather than dollars, so the number that "
      "counts is speed.")
    p()
    p("| search | what it looks for | conclusive? | candidates examined | findings |")
    p("|---|---|---|---|---|")
    by_name = {v["name"]: v for v in data["hunt"]}
    for name, (cosa, conclusiva, found) in HUNT.items():
        v = by_name.get(name, {})
        st_ = v.get("state") or v.get("result") or {}
        es = st_.get("examined")
        p(f"| `{name}` | {cosa} | {conclusiva} | "
          f"{es if es is not None else '—'} | **{found}** |")
    p()
    reg = ROOT / "runs/hunt/euclide_squarefree/search.log"
    if reg.is_file():
        last = None
        for line in reg.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("{") and "progress" in line:
                try:
                    last = json.loads(line)
                except ValueError:
                    pass
        if last and last.get("seconds"):
            v = last["examined"] / last["seconds"]
            def sp(x) -> str:
                return f"{x:,}".replace(",", " ")
            p(f"**MEASURED** — the Euclid-number search examined "
              f"{sp(last['examined'])} primes in {sp(last['seconds'])} "
              f"seconds, that is **{v:.0f} candidates per second** on one core, and "
              f"reached the prime {sp(last.get('current_prime', 0))} with nothing "
              f"found: for each of those primes ALL primorials with smaller factors "
              f"were checked, so the check is complete, not partial. With 8 searches in "
              f"parallel and an 8-hour night, that is about {v*8*3600/1e6:.1f} million "
              f"candidates per search per night (**ESTIMATED**: measured speed, "
              f"extrapolated over time).")
    p()
    p("**MEASURED** — a complete Lean verification costs 32.9 s with the sandbox and "
      "the fingerprint, 25.0 s without. With 4 verifications in parallel that is about "
      "440 verifications per hour: this, not the API, is the limit on how many proofs "
      "can be checked in a day.")
    p()
    probe = data["probe"]
    if probe:
        # The same rule as scripts/probe_lean.py: `plausible` that finds no
        # counterexample leaves a `sorry` and the file compiles anyway, so it is not a
        # closure.
        def notable(v: dict) -> bool:
            for pr in v["trials"]:
                if pr["result"] not in ("closed", "counterexample"):
                    continue
                m = pr.get("messages") or ""
                if ("declaration uses 'sorry'" in m
                        or "Unable to find a counter-example" in m):
                    continue
                return True
            return False

        notable = [v for v in probe if notable(v)]
        n = len(probe)
        low, high = clopper_pearson(len(notable), n)
        p(f"**MISURATO** — probe automatica su {n} enunciati open_problems discreti "
          f"(`decide`, `plausible`, `norm_num`, `simp_arith`, forma diritta e "
          f"and negated form, {8*n} attempts in all): **{len(notable)}** produced "
          f"anything. 90% Clopper-Pearson interval on the "
          f"fraction of open problems that fall on their own: {low:.1%} – {high:.1%}.")
        for v in notable:
            p(f"  - `{v['problem']}`: {v.get('ATTENZIONE', 'da esaminare')}")
        if not notable:
            p("  None. One apparent case — `Arxiv.«2107.12475».CollatzLike` — was "
              "`plausible` writing \"Unable to find a counter-example\" and leaving a "
              "`sorry`: the file compiled, but proved nothing. The verdict rule was "
              "corrected (`scripts/probe_lean.py`).")
    else:
        p("**In progress** — the automatic probe on 30 discrete open statements has "
          "not finished yet; when it does, its result updates the upper bound used in "
          "strategy A's optimistic scenario.")
    p()

    # ---------------------------------------------------------------- 6
    p("## 6. What cannot be estimated")
    p()
    p("1. **The probability that an open problem is solvable by this system.** It is "
      "the number that decides everything, and it is exactly the one I do not have. No "
      "sample of solved open problems exists on which to measure it: if it did, those "
      "problems would not be open. The three scenarios in section 4 are my hypotheses, "
      "not measurements.")
    p()
    p("2. **Why calibrating on solved problems is optimistic.** A problem with its "
      "proof in the archive has, by construction, a short proof: the eleven used here "
      "run from 1 to 34 lines. Whoever wrote the statement already knew it closed, and "
      "formalised it so that it would. On an open problem there is no guarantee that a "
      "short proof exists, nor that the statement is phrased in an attackable form. "
      "The measured 71% (5 of 7) is the rate on a population that contains NO open "
      "problem.")
    p()
    p("3. **Memorisation.** I chose problems that entered the archive after the "
      "declared training cutoff, but the cutoff concerns the archive, not the "
      "mathematics: Fermat's quadruple and the 17-vertex counterexample have been in "
      "the literature for decades. How much of the 9 successes is reconstruction and "
      "how much is recall, I cannot measure.")
    p()
    p("4. **How much the iteration limit matters.** One of the two failures stopped "
      "because it ran out of its 20 iterations, not because it could not do it: with "
      "60 iterations it might have closed. I have not tried, so I do not count it.")
    p()
    p("5. **The value of a finding.** If a search finds a counterexample, the protocol "
      "in `docs/04-finding-protocol.md` foresees three outcomes: faulty formalisation, "
      "already-known result, new candidate. With zero findings so far I have no data "
      "on how they would divide, and the likeliest case a priori is the first.")
    p()

    # ---------------------------------------------------------------- 7
    p("## 7. Raccomandazione")
    p()
    p(f"**The mixed strategy (C), and below ${1.0*c_c*n_targets:,.0f} there is no "
      f"reason di fare other.** Tre ragioni, in order di weight.")
    p()
    p(f"1. *The sieve costs almost nothing and covers everything.* A single shot at "
      f"one problem costs ${c_it1:.4f}, **MEASURED**. With **$50** you get "
      f"{50/c_it1:.0f} single shots: more than the archive's {n_targets} verifiable "
      f"open problems. That is, fifty dollars tries EVERY open problem in the "
      f"collection once, and shows where the model has a plan and where it does not. "
      f"No other spending in this project has a comparable "
      f"informazione/prezzo simile.")
    p()
    # advantage of the mixed strategy, realistic scenario
    m = AMPLIFICATION["realistic"]
    resa_a = 1.0 / c_fall
    resa_c = (FIRST_SHOT_SHARE + DIVE_SHARE * m) / (c_it1 + DIVE_SHARE * c_fall)
    p(f"2. *Full attempts should be bought afterwards, not before.* An attempt costs "
      f"${c_fall:.2f}, **MEASURED**, and ends unsolved almost every time. Buying one "
      f"for each of the {n_targets} open problems costs ${fmt(n_targets*c_fall)} and is "
      f"the worst way to spend it. Sieving all of them and attacking the best "
      f"{int(DIVE_SHARE*n_targets)} costs "
      f"${fmt(n_targets*(c_it1 + DIVE_SHARE*c_fall))} and, in the realistic scenario, "
      f"returns **{resa_c/resa_a:.1f} times** the successes per dollar of strategy A.")
    p()
    p("3. *Local computation is free: always saturate it.* Hunting counterexamples "
      "consumes no API budget, only machine-nights. It should be kept running "
      "alongside any strategy, because its marginal cost in dollars is zero. But it "
      "has to be aimed at the few problems where the published bounds are low: where "
      "the literature has reached 10^22, no night of computation changes anything.")
    p()
    p("**At what level of spending it makes sense to attempt the open problems.**")
    p()
    def attesi_c(b: float, scen: str) -> float:
        """Successes expected from strategy C, with section 4's caps."""
        p_a = SCENARIOS["A"][scen][0]
        m = AMPLIFICATION[scen]
        n_scr = min(n_targets, b / c_it1)
        resto = max(0.0, b - n_scr * c_it1)
        n_dive = min(n_scr, resto / c_fall)
        head = min(n_dive, DIVE_SHARE * n_scr)
        return (n_scr * FIRST_SHOT_SHARE * p_a + head * m * p_a
                + (n_dive - head) * p_a)

    def terna(b: float) -> str:
        return " / ".join(fmt(attesi_c(b, sc)) for sc in
                          ("optimistic", "realistic", "pessimistic"))

    p(f"- **$53** — the complete sieve: one shot at all "
      f"{n_targets} open_problems verificabili. Successi expected {terna(53)} "
      f"(ottimistico / realistico / pessimistico). Ha senso comunque, also "
      f"expecting zero successes: what you buy is the map of where the model has a "
      f"plan.")
    p(f"- **$174** — the complete sieve plus full attempts on the best "
      f"{DIVE_SHARE:.0%}. Expected successes {terna(174)}. This is the point where, if "
      f"the realistic scenario is right, a success becomes more likely than not. Below "
      f"it there is no reason to do anything else; above it, you are betting on a "
      f"number nobody knows.")
    p(f"- **$500** — expected successes {terna(500)}. Worth it only if the "
      f"setaccio da $53 ha mostrato targets promettenti: spent alla cieca, "
      f"it buys attempts on problems where the model had no plan at all.")
    p(f"- **$1000–$5000** — expected successes {terna(1000)} and {terna(5000)}. "
      f"Past saturation the arithmetic loses meaning: it would buy second and third "
      f"attempts at the same problems, and the model treats them as independent of the "
      f"first, which they are not. I would not recommend it without reading the "
      f"sieve's data first.")
    p()
    p("Note the width: at every level of spending the three scenarios span two orders "
      "of magnitude. **The uncertainty is not in the arithmetic: it is all in the "
      "value of p**, which section 6 declares unestimable. Anyone giving a single "
      "number here is guessing.")
    p()
    p("**A recommendation about targets, not only about spending.** The "
      f"{idx['main']['solved_without_proof']} problems marcati `research solved` "
      f"but lacking a proof in the archive are an intermediate class: the mathematics "
      f"is known, the formalisation is missing. On those the success rate would be "
      f"REAL (the outcome can be checked), the result is useful to the archive, and "
      f"the risk of spending for nothing is far lower. If the goal is 'do useful "
      f"mathematical work with this system' rather than 'solve an open problem', that "
      f"is the route with the best ratio of cost to result — and the calibration in "
      f"hand describes it better than it describes the open problems.")
    p()
    return r


def main() -> int:
    data = load()
    r = report_text(data)
    r = report_part_two(data, r)
    r = report_part_three(data, r)
    text = "\n".join(r) + "\n"
    output = ROOT / "docs/06-model-costs.md"
    output.write_text(text, encoding="utf-8")
    print(text)
    print(f"(scritto in {output})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
