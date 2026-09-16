"""Tests of the verification's isolation and of the archive's integrity check.

Two defences, and both are needed:

1. `sandbox-exec` prevents the candidate's code, while it is compiled, from writing
   anywhere except the temporary module's own directory.
2. The archive's fingerprint, compared before and after every verification, notices
   if anything changed all the same.

The second is needed even if the first works: `sandbox-exec` is deprecated by Apple,
and on Linux (where the real `landrun` ought to be used) the code takes another
route. A check that does not depend on the isolation mechanism is worth more than one
that trusts it.

Why sabotage cannot corrupt the verification in progress: comparator exports the
Challenge BEFORE compiling the Solution. So sabotage during the candidate's
compilation does not alter the current verification but the ones after it — which is
precisely comparator's assumption 2 ("you must not have ALREADY compiled potentially
adversarial files"). Here verifications run one after another in the same directory,
so that assumption has to be checked, not taken on trust.
"""
import copy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import config
import fingerprint as fingerprint_module
import sandbox


def setup_module(module):
    if not sandbox.available():
        pytest.skip("sandbox-exec not available on this system", allow_module_level=True)
    if not config.ARCHIVE.is_dir():
        pytest.skip("archive not cloned", allow_module_level=True)


@pytest.fixture
def profile(tmp_path):
    writable = sandbox.writable_dirs(config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_path)
    for d in writable:
        d.mkdir(parents=True, exist_ok=True)
    return sandbox.write_profile(tmp_path / "trial.sb", writable, ROOT)


def _write_test(path: Path, profile: Path | None) -> bool:
    """Tenta di scrivere `path`. Ritorna True se ci riesce."""
    path.unlink(missing_ok=True)
    command = ["/bin/sh", "-c", f'echo trial > "{path}"']
    if profile is not None:
        command = sandbox.wrap(command, profile)
    subprocess.run(command, capture_output=True, text=True)
    succeeded = path.exists()
    path.unlink(missing_ok=True)
    return succeeded


# --- the sandbox -------------------------------------------------------------

def test_without_the_sandbox_writing_into_the_archive_succeeds():
    """The control. Without this test the two that follow would not show that it is
    the sandbox stopping the writes: they could be blocked by something else (file
    system permissions, for instance)."""
    assert _write_test(config.ARCHIVE / "PROVA_CONTROPROVA.txt", None), \
        "without the sandbox the write has to succeed, or the test proves nothing"


def test_the_sandbox_blocks_writes_into_the_archive(profile):
    assert not _write_test(config.ARCHIVE / "PROVA_SANDBOX.txt", profile)


def test_the_sandbox_blocks_writes_to_the_compiled_files(profile):
    """The target that matters: the compiled files comparator reads
    l'statement original."""
    compiled = config.ARCHIVE / ".lake" / "build" / "lib" / "lean" / "FormalConjectures"
    if not compiled.is_dir():
        pytest.skip("archive not compiled")
    assert not _write_test(compiled / "PROVA_SANDBOX.olean", profile)


def test_the_sandbox_allows_the_writes_that_are_needed(profile):
    """If it blocked these too, no verification could work at all."""
    inside = config.ARCHIVE / config.SANDBOX_SUBDIR / "prova_permesso.txt"
    assert _write_test(inside, profile)


def test_the_sandbox_blocks_the_network(profile):
    command = sandbox.wrap(
        ["/usr/bin/curl", "-s", "-m", "8", "-o", "/dev/null", "https://example.com"], profile)
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0, "curl must not be able to reach the network"


# --- l'fingerprint --------------------------------------------------------------

def test_the_fingerprint_is_stable():
    a = fingerprint_module.compute(config.ARCHIVE)
    b = fingerprint_module.compute(config.ARCHIVE)
    assert a.n_content_files > 100, "hundreds of archive files are expected"
    assert not fingerprint_module.compare(a, b), \
        "two consecutive fingerprints with no changes have to agree"


def test_the_fingerprint_detects_a_modified_file():
    a = fingerprint_module.compute(config.ARCHIVE)
    b = copy.deepcopy(a)
    which = next(iter(b.content))
    b.content[which] = "0" * 64
    differences = fingerprint_module.compare(a, b)
    assert differences and "MODIFIED" in differences[0]
    assert which in differences[0]


def test_the_fingerprint_detects_a_deleted_file():
    a = fingerprint_module.compute(config.ARCHIVE)
    b = copy.deepcopy(a)
    b.content.pop(next(iter(b.content)))
    assert any("DELETED" in d for d in fingerprint_module.compare(a, b))


def test_the_fingerprint_detects_a_change_in_the_dependencies():
    a = fingerprint_module.compute(config.ARCHIVE)
    b = copy.deepcopy(a)
    b.dependency_metadata = "0" * 64
    assert any("Mathlib" in d for d in fingerprint_module.compare(a, b))


def test_the_fingerprint_ignores_the_temporary_modules_directory():
    """The candidate's directory changes at every verification: if we counted it,
    every verification would raise a false alarm."""
    folder = config.ARCHIVE / config.SANDBOX_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    a = fingerprint_module.compute(config.ARCHIVE, exclude=folder.name)
    intruder = folder / "S99.lean"
    intruder.write_text("-- file temporaneo\n", encoding="utf-8")
    try:
        b = fingerprint_module.compute(config.ARCHIVE, exclude=folder.name)
        assert not fingerprint_module.compare(a, b)
    finally:
        intruder.unlink(missing_ok=True)
