"""Build the harmonized panels:  python -m ipeds_clean.harmonize

Requires the cleaning stage first (python -m ipeds_clean).

Outputs (data/ipeds/harmonized/)
  completions.parquet        unitid x year x award_level x cip2020, men/women/total
  directory.parquet          unitid x year institution attributes
  cip_chain.csv              every original code -> CIP-2020, with method + path
  cip_chain_review.csv       every non-official step (title matches etc.) for audit
  qa_completions.csv         totals preserved per year/level; detail vs reported totals
  national_totals.csv        awards by year x award level (sanity check vs. Digest)
  enrollment.parquet         unitid x year x level x attendance x race x sex (fall enrollment)
  enrollment_first_time.parquet  first-time degree-seeking undergrads (subset of ug)
  completions_race.parquet   unitid x year x award_level x cip2020_2 x race x sex (1990+)
  qa_enrollment.csv, qa_completions_race.csv
  finance.parquet            unitid x fiscal year, harmonized revenue/expense concepts (nominal $)
  faculty_salaries.parquet   unitid x year x rank x contract x sex: n_faculty, salary_outlay, n_tenured
  grad_rates.parquet         unitid x year x cohort x measure x race x sex (2000/2010/2020)
  qa_finance.csv, qa_salaries.csv, qa_grad_rates.csv
  prices.parquet             unitid x academic year: published tuition & fees, room & board, books
  student_aid.parquet        unitid x year: aid to full-time first-time undergrads (2000/2010/2020)
  qa_prices.csv, qa_student_aid.csv
"""
from __future__ import annotations

import pandas as pd

from ..config import OUT
from . import (completions, completions_race, directory, enrollment, extras, finance, grad_rates, prices,
               reporting, salaries, student_aid)

HARM = OUT / "harmonized"


def main() -> None:
    HARM.mkdir(parents=True, exist_ok=True)
    panel, chain, review, qa = completions.build()
    panel.to_parquet(HARM / "completions.parquet", index=False)
    chain.to_csv(HARM / "cip_chain.csv", index=False)
    review.to_csv(HARM / "cip_chain_review.csv", index=False)
    qa.to_csv(HARM / "qa_completions.csv", index=False)

    d = directory.build(panel[["year", "unitid", "award_level", "total"]])
    d.to_parquet(HARM / "directory.parquet", index=False)

    nat = (panel.groupby(["year", "award_level"], observed=True)["total"].sum()
           .unstack("year").round(0))
    nat.to_csv(HARM / "national_totals.csv")

    # ---- console report
    ok = (qa["raw_detail"] - qa["harmonized"]).abs().max()
    print(f"completions: {len(panel):,} rows; max total drift through CIP chain = {ok:.6f}")
    m = qa.dropna(subset=["reported_99_total"])
    print(f"detail rows vs institution-reported totals (99 rows): "
          f"{(m.raw_detail == m.reported_99_total).mean():.1%} of year x level cells match exactly; "
          f"residual rows added: {qa.residual_added.sum():,.0f} awards "
          f"({qa.groupby('year').residual_added.sum().to_dict()})")
    w = panel.groupby(["year", "cip_method"])["total"].sum().unstack(fill_value=0)
    print("\nshare of awards by CIP mapping method:")
    print((w.div(w.sum(axis=1), axis=0) * 100).round(2).to_string())
    print("\nawards by year x harmonized level (thousands):")
    print((nat.fillna(0) / 1000).round(0).astype(int).to_string())
    j = panel[["year", "unitid"]].drop_duplicates().merge(d[["year", "unitid"]], how="left", indicator=True)
    print("\ncompletions institutions found in directory:",
          j.groupby("year")["_merge"].apply(lambda s: f"{(s == 'both').mean():.1%}").to_dict())
    print(f"directory: {len(d):,} rows, {d.unitid.nunique():,} institutions, {d.year.nunique()} years")

    # ---- enrollment
    enr, ft, eqa = enrollment.build()
    enr.to_parquet(HARM / "enrollment.parquet", index=False)
    ft.to_parquet(HARM / "enrollment_first_time.parquet", index=False)
    eqa.to_csv(HARM / "qa_enrollment.csv", index=False)
    print(f"\nenrollment: {len(enr):,} rows")
    print(eqa.to_string(index=False))
    print((enr.groupby(["year", "level"]).n.sum().unstack() / 1e6).round(2).to_string())

    # ---- completions by race
    cr, _ = completions_race.build()
    cr.to_parquet(HARM / "completions_race.parquet", index=False)
    a = cr.groupby(["year", "award_level"], observed=True)["n"].sum()
    b = panel.groupby(["year", "award_level"], observed=True)["total"].sum()
    rq = pd.DataFrame({"race_file": a, "panel": b}).dropna(subset=["race_file"])
    rq["diff"] = rq.race_file - rq.panel
    rq.reset_index().to_csv(HARM / "qa_completions_race.csv", index=False)
    print(f"\ncompletions_race: {len(cr):,} rows; max |race total - panel total| by year x level = "
          f"{rq['diff'].abs().max():.2f}")


    # ---- finance, salaries, graduation rates
    fin, fqa = finance.build()
    fin.to_parquet(HARM / "finance.parquet", index=False)
    fqa.to_csv(HARM / "qa_finance.csv", index=False)
    print(f"\nfinance: {len(fin):,} institution-years; forms: "
          f"{fin.groupby(['year', 'form']).size().unstack(fill_value=0).to_dict('index')}")
    print(fqa.to_string(index=False))

    sal, sqa = salaries.build()
    sal.to_parquet(HARM / "faculty_salaries.parquet", index=False)
    sqa.to_csv(HARM / "qa_salaries.csv", index=False)
    print(f"\nfaculty_salaries: {len(sal):,} rows (IPEDS has no 2000 salary file)")
    print(sqa.to_string(index=False))
    eq = salaries.equated_9month(sal, ["year"])
    print("avg salary, equated 9-month, all ranks:", eq.set_index("year").avg_salary_eq9.round(0).to_dict())

    gr, gqa = grad_rates.build()
    gr.to_parquet(HARM / "grad_rates.parquet", index=False)
    gqa.to_csv(HARM / "qa_grad_rates.csv", index=False)
    print(f"\ngrad_rates: {len(gr):,} rows")
    print(gqa.to_string(index=False))
    r = grad_rates.rates(gr, ["year"], "ba4", "comp150_bach")
    print("bachelor's 6-yr rate (ba4):", r.set_index("year").rate.round(3).to_dict())


    # ---- published prices, student aid
    pr, pqa = prices.build(d)
    pr.to_parquet(HARM / "prices.parquet", index=False)
    pqa.to_csv(HARM / "qa_prices.csv", index=False)
    print(f"\nprices: {len(pr):,} rows; academic years {sorted(pr.ay.unique())}")
    print(pqa.to_string(index=False))

    sa, aqa = student_aid.build()
    sa.to_parquet(HARM / "student_aid.parquet", index=False)
    aqa.to_csv(HARM / "qa_student_aid.csv", index=False)
    print(f"\nstudent_aid: {len(sa):,} institution-years")
    print(aqa.to_string(index=False))

    # ---- directory fill-ins for institution-years present in any panel but not in that
    #      year's directory file (mainly 1987-1992 header files and prior-year prices)
    pairs = pd.concat([panel[["year", "unitid"]], enr[["year", "unitid"]], fin[["year", "unitid"]],
                       sal[["year", "unitid"]], gr[["year", "unitid"]], sa[["year", "unitid"]],
                       pr[["ay", "unitid"]].rename(columns={"ay": "year"})])
    n0 = len(d)
    d = directory.fill_missing(d, pairs)
    d = directory.add_cn_sample(d, pairs)
    d = directory.add_title_iv(d)
    d.to_parquet(HARM / "directory.parquet", index=False)
    print(f"\ndirectory: added {len(d) - n0:,} filled institution-years (derivation = filled_from_<year>)")

    # ---- reporting structure, mergers
    rep = reporting.build()
    rep.to_parquet(HARM / "reporting.parquet", index=False)
    ent = reporting.entities(d)
    ent.to_parquet(HARM / "entities.parquet", index=False)
    print(f"\nreporting: {len(rep):,} rows; children with a parent: "
          f"{int((rep.prch.isin([2, 3]) & rep.parent_unitid.notna()).sum()):,}; merged unitids: {len(ent):,}")

    # ---- additional panels
    extra = {
        "admissions": extras.admissions, "retention": extras.retention,
        "fte": lambda: extras.fte(enr), "enrollment_12mo": extras.enrollment_12mo,
        "enrollment_age": extras.enrollment_age, "residence": extras.residence, "staff": extras.staff,
        "outcome_measures": extras.outcome_measures, "gr200": extras.gr200, "gr_pell": extras.gr_pell,
        "distance_ed": extras.distance_ed, "libraries": extras.libraries,
    }
    for name, fn in extra.items():
        x = fn()
        x.to_parquet(HARM / f"{name}.parquet", index=False)
        print(f"{name}: {len(x):,} rows, {x.year.min()}-{x.year.max()}")
    cb, cc = extras.completers()
    cb.to_parquet(HARM / "completers_race.parquet", index=False)
    cc.to_parquet(HARM / "completers_age.parquet", index=False)
    print(f"completers_race: {len(cb):,} rows; completers_age: {len(cc):,} rows")
    extras.variable_catalog(["outcome_measures", "gr200", "gr_pell", "completers_race", "completers_age",
                             "distance_ed", "libraries"]).to_csv(HARM / "extras_variables.csv", index=False)

    # ---- related sources (run only when their inputs are present)
    from ..config import ROOT
    if (ROOT / "sources" / "carnegie").exists():
        from . import carnegie
        lo, det, labs = carnegie.build()
        lo.to_parquet(HARM / "carnegie.parquet", index=False)
        det.to_parquet(HARM / "carnegie_detail.parquet", index=False)
        labs.to_csv(HARM / "carnegie_labels.csv", index=False)
        print(f"\ncarnegie: {len(lo):,} rows, editions {sorted(lo.cc_year.dropna().unique().tolist())}")
    if (ROOT / "sources" / "delta_cost").exists():
        from . import delta_cost
        dc = delta_cost.read()
        dc.to_parquet(HARM / "delta_cost.parquet", index=False)
        delta_cost.variables().to_csv(HARM / "delta_cost_variables.csv", index=False)
        delta_cost.compare(dc).to_csv(HARM / "qa_delta_cost.csv", index=False)
        print(f"delta_cost: {len(dc):,} rows, {dc.year.min()}-{dc.year.max()}")
        del dc
    if (OUT / "digest" / "values.parquet").exists():
        from . import digest_benchmarks
        q = digest_benchmarks.build()
        q.to_csv(HARM / "qa_digest.csv", index=False)
        print(f"qa_digest: {q.measure.nunique()} measures; within 1% of the Digest: "
              f"{(q.diff_pct.abs() <= 1).mean():.0%} of measure-years")

    print(f"\nwrote -> {HARM}")


if __name__ == "__main__":
    main()
