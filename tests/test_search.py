"""
Tests of the infrastructure for long searches (verifier/search.py).

The three things that have to work, because without them an eight-hour search
is unusable:
    * isolation (no network, no writes outside the directory);
  * the checkpoint, written so that an interruption cannot corrupt it;
  * resumption, which has to start from where it got to and not from scratch.
"""
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import config
import search as search_module
import sandbox


def setup_module(module):
    if not sandbox.available():
        pytest.skip("sandbox-exec not available", allow_module_level=True)


#: A minimal search program that honours the contract.
COUNTING_PROGRAM = '''
import json, os, signal, sys, time

checkpoint = os.environ["SEARCH_CHECKPOINT"]
state = os.environ["SEARCH_STATE"]
UP_TO = int(os.environ.get("UP_TO", "50"))

n = 0
found = []
if os.path.exists(checkpoint):
    d = json.load(open(checkpoint))
    n = d.get("position", 0)
    found = d.get("found", [])

stopped = False
def stop(s, f):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop)

def salva():
    tmp = state + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"position": n, "examined": n, "found": found}, f)
    os.replace(tmp, state)

while n < UP_TO and not stopped:
    n += 1
    if n % 17 == 0:
        found.append({"n": n})
        print(json.dumps({"event": "found", "detail": {"n": n}}), flush=True)
    if n % 10 == 0:
        salva()
        print(json.dumps({"event": "progress", "position": n, "examined": n}), flush=True)
    time.sleep(float(os.environ.get("PAUSE", "0.01")))

salva()
print(json.dumps({"event": "end", "position": n, "examined": n}), flush=True)
'''


def test_a_search_runs_to_completion(tmp_path):
    r = search_module.Search("counting_trial", COUNTING_PROGRAM, folder=tmp_path / "count",
                               variables={"UP_TO": 50})
    result = r.run(verbose=False)
    assert result.completed, f"not completed: {result.to_json()}"
    assert result.position == 50
    assert result.examined == 50
    assert {"n": 17} in result.found
    assert {"n": 34} in result.found


def test_the_variables_reach_the_program(tmp_path):
    """The child's environment is deliberately minimal: no API key, no project
    PATH. The variables have to be passed explicitly."""
    program = """
import json, os
v = os.environ.get("MY_PARAMETER", "absent")
key = "present" if "ANTHROPIC_API_KEY" in os.environ else "absent"
with open(os.environ["SEARCH_STATE"], "w") as f:
    json.dump({"position": v, "examined": 1, "found": [key]}, f)
"""
    r = search_module.Search("variables_trial", program, folder=tmp_path / "var",
                               variables={"MY_PARAMETER": "hello"})
    result = r.run(verbose=False)
    assert result.position == "hello"
    assert result.found == ["absent"], "the API key must not be visible"


def test_the_checkpoint_is_written(tmp_path):
    r = search_module.Search("checkpoint_trial", COUNTING_PROGRAM, folder=tmp_path / "ckpt",
                               variables={"UP_TO": 30})
    r.run(verbose=False)
    assert r.checkpoint_file.is_file()
    d = json.loads(r.checkpoint_file.read_text())
    assert d["position"] == 30


def test_resuming_starts_from_where_it_got_to(tmp_path):
    """The most important point: after an interruption it does not start over."""
    folder = tmp_path / "resumption"
    r = search_module.Search("resumption_trial", COUNTING_PROGRAM, folder=folder,
                               variables={"UP_TO": 100000, "PAUSE": 0.02})
    first = r.run(max_seconds=2.0, verbose=False)
    assert first.interrupted, "expected an interruption on the time limit"
    assert first.position > 0, "it must have done something before stopping"
    reached = first.position

    # second run: it has to RESUME
    r.variables = {"UP_TO": reached + 30, "PAUSE": 0.001}
    second = r.run(verbose=False)
    assert second.completed
    assert second.position == arrivato + 30
    # had it started over, the time would have been far longer
    assert second.examined == arrivato + 30


def test_riprendi_falso_ricomincia_da_capo(tmp_path):
    folder = tmp_path / "restart"
    r = search_module.Search("restart_trial", COUNTING_PROGRAM, folder=folder,
                               variables={"UP_TO": 20, "PAUSE": 0.001})
    r.run(verbose=False)
    r.variables = {"UP_TO": 10, "PAUSE": 0.001}
    second = r.run(resume=False, verbose=False)
    assert second.position == 10, "with resume=False it has to start from zero"


NETWORK_PROGRAM = '''
import json, os, urllib.request
try:
    urllib.request.urlopen("http://example.com", timeout=5)
    print(json.dumps({"event": "found", "detail": "NETWORK REACHABLE"}), flush=True)
except Exception as e:
    print(json.dumps({"event": "progress", "position": 0, "network": type(e).__name__}), flush=True)
with open(os.environ["SEARCH_STATE"], "w") as f:
    json.dump({"position": 0, "examined": 0, "found": []}, f)
'''


def test_the_search_has_no_network_access(tmp_path):
    r = search_module.Search("network_trial", NETWORK_PROGRAM, folder=tmp_path / "network")
    result = r.run(verbose=False)
    assert "NETWORK REACHABLE" not in str(result.found), "the network has to be blocked"


WRITE_PROGRAM = '''
import json, os
target = os.environ.get("TARGET", "/tmp/write_outside_trial.txt")
try:
    open(target, "w").write("x")
    result = "WRITE SUCCEEDED"
except Exception as e:
    result = type(e).__name__
print(json.dumps({"event": "progress", "position": 0, "write": result}), flush=True)
with open(os.environ["SEARCH_STATE"], "w") as f:
    json.dump({"position": 0, "examined": 0, "found": [result]}, f)
'''


def test_the_search_does_not_write_outside_its_directory(tmp_path):
    r = search_module.Search("write_trial", WRITE_PROGRAM,
                               folder=tmp_path / "write_op",
                               variables={"TARGET": str(config.ROOT / "SEARCH_WRITE_OUTSIDE_TRIAL.txt")})
    result = r.run(verbose=False)
    assert "WRITE SUCCEEDED" not in str(result.found)
    assert not (config.ROOT / "SEARCH_WRITE_OUTSIDE_TRIAL.txt").exists()


def test_the_search_can_use_numpy_and_sympy(tmp_path):
    """This is exactly what the computation environment is for."""
    program = '''
import json, os
import numpy as np, sympy
v = int(np.sum(np.arange(101)))
p = int(sympy.prime(1000))
print(json.dumps({"event": "progress", "position": v, "first": p}), flush=True)
with open(os.environ["SEARCH_STATE"], "w") as f:
    json.dump({"position": v, "examined": 1, "found": [p]}, f)
'''
    r = search_module.Search("libraries_trial", program, folder=tmp_path / "lib")
    result = r.run(verbose=False)
    assert result.position == 5050, f"numpy: {result.to_json()}"
    assert 7919 in result.found, "sympy.prime(1000) = 7919"
