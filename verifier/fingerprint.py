"""
Fingerprint of the archive's compiled files.

WHY
---
comparator's README lists among its assumptions (number 2):

    "You have not previously tried to compile the Solution file or any other
    potentially adversarial files (as that might compromise your Challenge
    file to make it seem like you are looking for a different proof than you
    actually are)"

In other words: if compiling the candidate's file rewrote the archive's compiled
files, the "Challenge" comparator exports would no longer be the original
statement, and the verification would compare the solution against an altered
problem. Everything would pass, and it would mean nothing.

Here verifications run one after another in the same directory, so that
assumption cannot be taken on trust: it has to be checked. This module takes a
fingerprint of the archive before and after every verification.

HOW
---
Two levels, chosen by measuring the real costs:

  * the archive's files (its 786 .olean files and 795 sources, 126 MB in all) are
    hashed by CONTENT, one at a time. It costs 0.65 seconds and makes it possible
    to say *which* file changed;
  * Mathlib and the other dependencies (7877 .olean files, 6.8 GB) would be far
    too slow to hash in full, so their METADATA are taken instead (path, size,
    modification time to the nanosecond). It costs 0.86 seconds and catches any
    rewrite.

About a second and a half in total, on a verification that lasts twenty-five.
"""
from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

#: How many threads to use for hashing. `hashlib` releases the GIL while it
#: works, so threads really do help here: from 3.2 seconds to under one.
N_THREAD = min(8, (os.cpu_count() or 4))


@dataclass
class Fingerprint:
    #: relative path -> sha256 of the content (the archive's files)
    content: dict[str, str] = field(default_factory=dict)
    #: a single digest for the dependencies' metadata (Mathlib and the rest)
    dependency_metadata: str = ""
    n_content_files: int = 0
    n_metadata_files: int = 0


def _archive_dirs(archive: Path) -> list[Path]:
    """The files that define the statement: the archive's compiled files and sources."""
    return [
        archive / ".lake" / "build" / "lib" / "lean",
        archive / "FormalConjectures",
        archive / "FormalConjecturesForMathlib",
    ]


def _dependency_dirs(archive: Path) -> list[Path]:
    return [archive / ".lake" / "packages"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def compute(archive: Path, exclude: str = "_Judge") -> Fingerprint:
    """Take the fingerprint. `exclude` is the name of the temporary module's
    directory, which by definition changes at every verification."""
    imp = Fingerprint()

    to_hash: list[Path] = []
    for root in _archive_dirs(archive):
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != exclude]
            to_hash.extend(Path(dirpath) / name for name in filenames)

    def one(p: Path) -> tuple[str, str] | None:
        try:
            return str(p.relative_to(archive)), _sha256(p)
        except OSError:
            return None

    with ThreadPoolExecutor(max_workers=N_THREAD) as pool:
        for result in pool.map(one, to_hash):
            if result is not None:
                imp.content[result[0]] = result[1]
    imp.n_content_files = len(imp.content)

    entries: list[str] = []
    cut = len(str(archive)) + 1
    for root in _dependency_dirs(archive):
        if root.is_dir():
            _metadata_recursive(str(root), cut, exclude, entries)
    entries.sort()
    h = hashlib.sha256()
    for v in entries:
        h.update(v.encode())
    imp.dependency_metadata = h.hexdigest()
    imp.n_metadata_files = len(entries)
    return imp


#: Directories irrelevant to the statement: Mathlib's `.git` alone holds tens of
#: thousands of files and is never read by Lean.
_IGNORED_DIRS = {".git", ".github"}


def _metadata_recursive(folder: str, cut: int, exclude: str, entries: list[str]) -> None:
    """Collect path, size and modification time.

    Uses `os.scandir` and strings rather than `os.walk` with `Path` objects: over
    111,000 files the measured difference is between 0.3 and 3 seconds, and this
    function runs twice per verification.
    """
    try:
        iterator = os.scandir(folder)
    except OSError:
        return
    with iterator:
        for entry in iterator:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name != exclude and entry.name not in _IGNORED_DIRS:
                        _metadata_recursive(entry.path, cut, exclude, entries)
                else:
                    st = entry.stat(follow_symlinks=False)
                    entries.append(f"{entry.path[cut:]}|{st.st_size}|{st.st_mtime_ns}")
            except OSError:
                continue


def compare(before: Fingerprint, after: Fingerprint, max_listed: int = 12) -> list[str]:
    """A readable list of the differences. Empty if the archive is intact."""
    differences: list[str] = []

    modified = [p for p, d in after.content.items()
                  if p in before.content and before.content[p] != d]
    vanished = [p for p in before.content if p not in after.content]
    appeared = [p for p in after.content if p not in before.content]

    def list_them(label: str, which_ones: list[str]) -> None:
        if not which_ones:
            return
        shown = ", ".join(sorted(which_ones)[:max_listed])
        rest = f" (and {len(which_ones) - max_listed} more)" if len(which_ones) > max_listed else ""
        differences.append(f"{label}: {shown}{rest}")

    list_them(f"{len(modified)} archive files MODIFIED", modified)
    list_them(f"{len(vanished)} archive files DELETED", vanished)
    list_them(f"{len(appeared)} NEW files inside the archive", appeared)

    if before.dependency_metadata != after.dependency_metadata:
        differences.append(
            f"the files of Mathlib and the other dependencies have changed "
            f"(before: {before.n_metadata_files} files, after: {after.n_metadata_files})")
    return differences
