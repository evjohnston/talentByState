"""Manifest of the input files that git does not track (sources/, reference/digest/, reference/survey_forms/).

    python -m ipeds_clean.manifest            # check the inputs against manifests/sources_manifest.csv
    python -m ipeds_clean.manifest --update   # record the current inputs (after adding or moving files on purpose)

The manifest (tracked in git) lists every input file with its size and MD5. A check reports files that are
missing, new, or changed (different size or MD5), so a deleted, truncated or overwritten source is visible before a
rebuild uses it. Moving files on purpose (for example into sources/_duplicates_to_delete/) is expected: run
--update afterwards and commit the manifest, so the git history records what changed and when.

MD5s are cached in cache/manifest_md5.csv by (path, size, modification time), so only new or touched files are
hashed again. The first run reads every file once; in iCloud Drive that also downloads files that are only stored
online, which can take a while. sources/_duplicates_to_delete/ is skipped (it is meant to be deleted).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

from .config import ROOT

ROOTS = [ROOT / "sources", ROOT / "reference" / "digest", ROOT / "reference" / "survey_forms"]
SKIP = {"_duplicates_to_delete", ".DS_Store"}
MANIFEST = ROOT / "manifests" / "sources_manifest.csv"
CACHE = ROOT / "cache" / "manifest_md5.csv"


def files() -> list[Path]:
    out = []
    for r in ROOTS:
        for p in r.rglob("*"):
            if p.is_file() and not (SKIP & set(p.relative_to(ROOT).parts)):
                out.append(p)
    return sorted(out)


def md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan() -> pd.DataFrame:
    cache = pd.read_csv(CACHE, dtype={"md5": str}) if CACHE.exists() else pd.DataFrame(columns=["path", "bytes", "mtime", "md5"])
    known = {(r.path, int(r.bytes), float(r.mtime)): r.md5 for r in cache.itertuples()}
    rows = []
    fs = files()
    for i, p in enumerate(fs, 1):
        st = p.stat()
        rel = p.relative_to(ROOT).as_posix()
        h = known.get((rel, st.st_size, st.st_mtime)) or md5(p)
        rows.append({"path": rel, "bytes": st.st_size, "mtime": st.st_mtime, "md5": h})
        if i % 500 == 0:
            print(f"  {i:,} / {len(fs):,} files", flush=True)
            pd.DataFrame(rows).to_csv(CACHE, index=False)           # keep progress if interrupted
    d = pd.DataFrame(rows)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(CACHE, index=False)
    return d[["path", "bytes", "md5"]]


def check(cur: pd.DataFrame) -> int:
    if not MANIFEST.exists():
        print("no manifest yet: run with --update")
        return 1
    old = pd.read_csv(MANIFEST, dtype={"md5": str})
    m = old.merge(cur, on="path", how="outer", suffixes=("_manifest", "_now"), indicator=True)
    missing = m[m._merge == "left_only"]
    new = m[m._merge == "right_only"]
    both = m[m._merge == "both"]
    changed = both[(both.bytes_manifest != both.bytes_now) | (both.md5_manifest != both.md5_now)]
    for label, d in (("MISSING", missing), ("NEW", new), ("CHANGED", changed)):
        for p in d.path:
            print(f"{label:8} {p}")
    print(f"{len(cur):,} files checked: {len(missing)} missing, {len(new)} new, {len(changed)} changed")
    return 1 if len(missing) or len(changed) else 0


if __name__ == "__main__":
    cur = scan()
    if "--update" in sys.argv:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        cur.to_csv(MANIFEST, index=False)
        print(f"wrote {MANIFEST.relative_to(ROOT)}: {len(cur):,} files, {cur.bytes.sum() / 1e9:.1f} GB")
    else:
        sys.exit(check(cur))
