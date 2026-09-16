"""The agent's log: the lines have to reach the file while it runs.

It exists for one reason, and it is not a technical one: whoever is watching from
another terminal has to be able to see that the work is progressing. Earlier the
report was written only at the end, and an hour-long run looked stuck.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "verifier"))

import agent


def test_it_writes_to_screen_and_file_line_by_line(tmp_path, capsys):
    log = tmp_path / "below" / "log.log"
    tee = agent._Tee(sys.stdout, log)
    tee.write("first line\n")
    # the line has to be on the file ALREADY, without waiting for a close
    assert log.read_text(encoding="utf-8") == "first line\n"
    tee.write("second line\n")
    assert log.read_text(encoding="utf-8").count("\n") == 2
    tee.flush()
    assert "first line" in capsys.readouterr().out


def test_it_creates_the_directory_if_missing(tmp_path):
    log = tmp_path / "a" / "b" / "c.log"
    agent._Tee(sys.stdout, log).write("x\n")
    assert log.is_file()


def test_it_does_not_break_when_asked_for_isatty(tmp_path):
    d = agent._Tee(sys.stdout, tmp_path / "r.log")
    assert d.isatty() in (True, False)
