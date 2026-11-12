"""Publish the State Talent Sheet and profiles (data/states/) to GitHub Pages.

    python -m ipeds_clean.deploy_pages          # copy data/states/ to the gh-pages branch and push it
    python -m ipeds_clean.deploy_pages --dry    # build the site folder and show what would be pushed

Site: https://evjohnston.github.io/talentByState/ (the root opens the profiles index; the sheet is sheet.html).

The site lives on its own branch, gh-pages, which holds only the built pages, not the code. Each deploy replaces
that branch with a single fresh commit (a forced push), so the repository does not grow by the size of the site
(~490 MB, mostly PDFs) on every rebuild. main is never touched. The site folder is built in
cache/pages_site.nosync/ (".nosync" keeps iCloud from syncing it).

Run it after a rebuild has been checked (see RULES.md: no browser errors, fonts embedded, even print page counts).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime

from .config import ROOT

SITE_SRC = ROOT / "data" / "states"
WORK = ROOT / "cache" / "pages_site.nosync"
BRANCH = "gh-pages"
URL = "https://evjohnston.github.io/talentByState/"
INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>State Talent Profiles</title><meta http-equiv="refresh" content="0; url=profiles/index.html">
<link rel="canonical" href="profiles/index.html"></head>
<body><p><a href="profiles/index.html">State Talent Profiles</a> · <a href="sheet.html">State Talent Sheet</a></p></body></html>
"""


def git(*args, cwd=WORK, check=True) -> str:
    r = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr}")
    return r.stdout.strip()


def build() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(SITE_SRC, WORK, ignore=shutil.ignore_patterns(".DS_Store"))
    if not (WORK / "index.html").exists():
        (WORK / "index.html").write_text(INDEX)
    (WORK / ".nojekyll").write_text("")          # serve files as they are (no Jekyll processing)
    big = [p for p in WORK.rglob("*") if p.is_file() and p.stat().st_size > 95_000_000]
    if big:
        raise SystemExit(f"files over GitHub's 100 MB limit: {[str(p.relative_to(WORK)) for p in big]}")


def deploy(dry: bool) -> None:
    build()
    remote = git("remote", "get-url", "origin", cwd=ROOT)
    name, email = git("config", "user.name", cwd=ROOT), git("config", "user.email", cwd=ROOT)
    src = git("rev-parse", "--short", "HEAD", cwd=ROOT)
    git("init", "-q", "-b", BRANCH)
    git("config", "user.name", name)
    git("config", "user.email", email)
    git("add", "-A")
    git("commit", "-q", "-m", f"Site build {datetime.now():%Y-%m-%d %H:%M} from main {src}")
    n = len(git("ls-files").splitlines())
    mb = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file() and ".git" not in p.parts) / 1e6
    print(f"site: {n:,} files, {mb:,.0f} MB")
    if dry:
        print(f"dry run: built {WORK}, not pushed")
        return
    git("push", "-q", "--force", remote, f"{BRANCH}:{BRANCH}")
    print(f"pushed {BRANCH}; live in a minute or two at {URL}")


if __name__ == "__main__":
    deploy("--dry" in sys.argv)
