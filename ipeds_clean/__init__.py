"""Cleaning pipeline for decennial IPEDS/HEGIS extracts. See README.md."""
from __future__ import annotations

import pandas as pd

from .config import CLEAN_DIR, META_DIR


def load(year: int, table: str, columns: list[str] | None = None) -> pd.DataFrame:
    """Load a cleaned table, e.g. load(2010, "ef2010a")."""
    return pd.read_parquet(CLEAN_DIR / str(year) / f"{table}.parquet", columns=columns)


def tables() -> pd.DataFrame:
    return pd.read_csv(META_DIR / "tables.csv")


def variables() -> pd.DataFrame:
    return pd.read_csv(META_DIR / "variables.csv")


def labels(year: int, table: str, varname: str) -> dict:
    """code -> label for one coded variable."""
    v = pd.read_csv(META_DIR / "value_labels.csv", dtype={"code": str})
    v = v[(v.year == year) & (v.table == table) & (v.varname == varname)]
    return dict(zip(v["code"], v["label"]))


def completions() -> pd.DataFrame:
    """Harmonized completions panel (build with: python -m ipeds_clean.harmonize)."""
    from .config import OUT
    return pd.read_parquet(OUT / "harmonized" / "completions.parquet")


def directory() -> pd.DataFrame:
    """Harmonized institution directory panel."""
    from .config import OUT
    return pd.read_parquet(OUT / "harmonized" / "directory.parquet")


def enrollment(first_time: bool = False) -> pd.DataFrame:
    """Harmonized fall enrollment (additive cells), or the first-time undergrad subset."""
    from .config import OUT
    f = "enrollment_first_time.parquet" if first_time else "enrollment.parquet"
    return pd.read_parquet(OUT / "harmonized" / f)


def completions_race() -> pd.DataFrame:
    """Harmonized completions by race/ethnicity, 2-digit CIP-2020, 1990-2020."""
    from .config import OUT
    return pd.read_parquet(OUT / "harmonized" / "completions_race.parquet")


def finance(real_base_year: int | None = None, index: str = "index") -> pd.DataFrame:
    """Harmonized finance; pass real_base_year=2020 for constant dollars (BLS CPI-U,
    crosswalks/deflators.csv). index="index_fy" uses the July-June fiscal-year average."""
    from .config import OUT
    df = pd.read_parquet(OUT / "harmonized" / "finance.parquet")
    if real_base_year:
        from .harmonize.finance import deflate
        df = deflate(df, real_base_year, index=index)
    return df


def faculty_salaries() -> pd.DataFrame:
    """FT instructional faculty counts and salary outlays (see harmonize.salaries.equated_9month)."""
    from .config import OUT
    return pd.read_parquet(OUT / "harmonized" / "faculty_salaries.parquet")


def grad_rates() -> pd.DataFrame:
    """Graduation Rate Survey counts (see harmonize.grad_rates.rates)."""
    from .config import OUT
    return pd.read_parquet(OUT / "harmonized" / "grad_rates.parquet")


def prices() -> pd.DataFrame:
    """Published tuition & fees, room & board, books by academic year."""
    from .config import OUT
    return pd.read_parquet(OUT / "harmonized" / "prices.parquet")


def student_aid() -> pd.DataFrame:
    """Aid to full-time first-time undergraduates (2000/2010/2020 files = 1999/2009/2019 aid years)."""
    from .config import OUT
    return pd.read_parquet(OUT / "harmonized" / "student_aid.parquet")


def panel(name: str) -> pd.DataFrame:
    """Any harmonized panel by name, e.g. panel("admissions"), panel("staff"), panel("reporting")."""
    from .config import OUT
    return pd.read_parquet(OUT / "harmonized" / f"{name}.parquet")


def carnegie(asof: pd.DataFrame | None = None) -> pd.DataFrame:
    """Carnegie classifications (unitid x edition). Pass a panel to attach, for each row, the
    latest edition at or before its year: ic.carnegie(ic.directory())."""
    from .harmonize.carnegie import carnegie_asof
    cc = panel("carnegie")
    return cc if asof is None else carnegie_asof(asof, cc=cc)


def delta_cost(columns: list[str] | None = None) -> pd.DataFrame:
    """Delta Cost Project 1987-2012 (unitid x year); see data/ipeds/harmonized/delta_cost_variables.csv."""
    from .config import OUT
    return pd.read_parquet(OUT / "harmonized" / "delta_cost.parquet", columns=columns)


def digest(series_id: str | None = None, edition: int | None = None, latest: bool = False) -> pd.DataFrame:
    """Digest of Education Statistics values (IPEDS/HEGIS tables), long format.
    series_id is the current table number ("303.10"); older editions are linked to it.
    latest=True keeps, for each row/column/year, the value from the newest edition
    published after that year (revised data, no projections)."""
    from .digest import load_values
    v = load_values(series_id, edition)
    if latest:
        v = v[v.year_last.isna() | (v.edition > v.year_last)]
        v = v.sort_values("edition").groupby(["series_id", "row_path", "col_label"], dropna=False).tail(1)
    return v


def digest_catalog() -> pd.DataFrame:
    """Every Digest table file: edition, table_id, title, source note, ipeds flag, series link."""
    from .config import OUT
    return pd.read_csv(OUT / "digest" / "catalog.csv")
