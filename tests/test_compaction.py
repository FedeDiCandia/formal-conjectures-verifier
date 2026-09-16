"""Compacting the context: without it, a long attempt dies of context.

Text only; the API is never called.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "verifier"))

import agent


def _conversation(n_iterations: int, length: int = 5000) -> list:
    """A fake conversation: the statement, then n rounds of tool use."""
    messages = [{"role": "user", "content": "THE PROBLEM'S STATEMENT"}]
    for i in range(n_iterations):
        messages.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": f"t{i}", "name": "lean_check",
             "input": {"lean_code": f"theorem trial{i} : True := trivial"}}]})
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"t{i}",
             "content": "ERROR " * (length // 7)}]})
    return messages


def test_it_shortens_the_old_results_and_leaves_the_recent_ones_intact():
    m = _conversation(20)
    before = sum(len(b["content"]) for msg in m if isinstance(msg["content"], list)
                 for b in msg["content"] if b.get("type") == "tool_result")
    cut = agent.compact_conversation(m, intact=8, tail=600)
    after = sum(len(b["content"]) for msg in m if isinstance(msg["content"], list)
                for b in msg["content"] if b.get("type") == "tool_result")
    assert cut > 0
    assert after < before / 3, f"compaction ineffective: {before} -> {after}"
    # the last four results (inside the 8 untouched messages) are whole
    latest = [b["content"] for msg in m[-8:] if isinstance(msg["content"], list)
              for b in msg["content"] if b.get("type") == "tool_result"]
    assert latest and all(len(c) > 600 for c in latest)


def test_the_statement_is_never_touched():
    m = _conversation(20)
    agent.compact_conversation(m)
    assert m[0]["content"] == "THE PROBLEM'S STATEMENT"


def test_the_code_the_model_wrote_stays_whole():
    m = _conversation(20)
    agent.compact_conversation(m)
    for msg in m:
        if isinstance(msg["content"], list):
            for b in msg["content"]:
                if b.get("type") == "tool_use":
                    assert b["input"]["lean_code"].startswith("theorem trial")


def test_it_is_idempotent():
    m = _conversation(20)
    first = agent.compact_conversation(m)
    second = agent.compact_conversation(m)
    assert first > 0 and second == 0


def test_a_short_conversation_is_left_alone():
    m = _conversation(3)
    assert agent.compact_conversation(m, intact=8) == 0
