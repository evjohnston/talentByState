"""Non-IPEDS sources, reshaped for the State Talent Sheet and the state profiles.

Each source module writes its own CSVs (data/acs, data/naep, data/gss, data/sed, data/h1b, data/dol,
data/patents; SEVIS has its own sheet_panel in sevis.py). This module reads those CSVs and returns, per
source, the sheet's long panel (state, year, measure, value; percentages as 0-100), the measure titles,
notes and the source line. A source whose outputs are missing is skipped.

Every value a source has is kept, for the 50 states + DC and the US, in every year it exists: a state missing
a year is blank in that year only. The sheet takes a measure's latest year as the last year any state reports,
so national-only years (NSF GSS after 2016) appear in the trend charts without blanking every state.
US is each source's national figure (see the notes for what it covers).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCES = {  # src key: (rail group, source line)
    "acs": ("Workforce: foreign-born STEM workers (ACS)", "Data from U.S. Census Bureau, American Community Survey"),
    "naep": ("K-12 preparation (NAEP)", "Data from NCES, National Assessment of Educational Progress"),
    "gss": ("Graduate students & postdocs (NSF GSS)", "Data from NSF NCSES, Survey of Graduate Students and Postdoctorates"),
    "sed": ("Doctorates (NSF SED)", "Data from NSF NCSES, Survey of Earned Doctorates"),
    "h1b": ("H-1B petitions by employer (USCIS)", "Data from USCIS, H-1B Employer Data Hub"),
    "dol": ("H-1B jobs & green cards (DOL)", "Data from DOL, Office of Foreign Labor Certification"),
    "patents": ("Patents (USPTO)", "Data from USPTO, PatentsView"),
    "migration": ("Graduate migration (ACS)", "Data from U.S. Census Bureau, American Community Survey"),
    "scorecard": ("Graduate earnings & debt (College Scorecard)", "Data from U.S. Department of Education, College Scorecard"),
    "k12": ("K-12 preparation (NAEP)", "Data from NCES, Digest of Education Statistics"),
    "opt": ("OPT: international graduates' first jobs (ICE)", "Data from ICE, SEVIS FOIA releases"),
    "j1": ("Exchange visitors (J-1)", "Data from U.S. Department of State, BridgeUSA"),
    "pseo": ("Do graduates stay? (Census PSEO)", "Data from U.S. Census Bureau, Post-Secondary Employment Outcomes"),
    "oews": ("STEM jobs & wages (BLS)", "Data from BLS, Occupational Employment and Wage Statistics"),
    "dhs": ("Green cards & citizenship (DHS)", "Data from DHS, Yearbook of Immigration Statistics"),
    "rd": ("Research funding (NSF HERD, Federal Funds, USAspending)", "Data from NSF NCSES, HERD and Federal Funds for R&D; USAspending.gov"),
    "iie": ("International students' economic value (IIE, NAFSA)", "Data from IIE, Open Doors; NAFSA, International Student Economic Value Tool"),
    "crdc": ("K-12 preparation (NAEP)", "Data from U.S. Department of Education, Civil Rights Data Collection"),
    "digest_ps": ("Student migration", "Data from NCES, Digest of Education Statistics"),
}
MONTHS: dict = {}   # measure -> {year: label} for sources whose "year" needs a label (single-release data)
PCT, N, USD = "%", "count", "nominal $"
F_PCT, F_N, F_USD, F_SCORE = "{:.1f}%", "{:,.0f}", "${:,.0f}", "{:.0f}"


def _long(w: pd.DataFrame, year: str, cols: dict, pct: set = frozenset(), scale: float = 100) -> pd.DataFrame:
    """Wide (year, state, cols...) -> long sheet rows; columns in pct are multiplied by scale."""
    out = []
    for src, name in cols.items():
        if src not in w:
            continue
        v = w[src] * (scale if src in pct else 1)
        out.append(pd.DataFrame({"state": w.state, "year": w[year].astype(int), "measure": name, "value": v}))
    return pd.concat(out, ignore_index=True).dropna(subset=["value"])


def _keep_states(d: pd.DataFrame, states: list[str]) -> pd.DataFrame:
    """Every value for the 50 states + DC and the US, every year a source has it (no year filter: a state missing
    a year is blank in that year only)."""
    return d[d.state.isin(states + ["US"])]


# ---------------------------------------------------------------- one function per source

def acs():
    m = {
        "acs_stem_workers": ("Workers in STEM occupations (ACS)", "workers", F_N),
        "acs_stem_share_of_workers": ("STEM workers as a share of all workers (ACS)", PCT, F_PCT),
        "acs_stem_fb_share": ("Foreign-born share of STEM workers (ACS)", PCT, F_PCT),
        "acs_stem_grad_fb_share": ("Foreign-born share of STEM workers with a graduate degree (ACS)", PCT, F_PCT),
        "acs_stem_phd_fb_share": ("Foreign-born share of STEM workers with a doctorate (ACS)", PCT, F_PCT),
        "acs_stem_noncit_share": ("Noncitizen share of STEM workers (ACS)", PCT, F_PCT),
        "acs_stem_fb_recent_share": ("STEM workers born abroad who arrived in the last 10 years (ACS)", PCT, F_PCT),
        "acs_stem_fb_india_share": ("Share of foreign-born STEM workers born in India (ACS)", PCT, F_PCT),
        "acs_fb_share": ("Foreign-born share of residents (ACS)", PCT, F_PCT),
        "acs_fb_share_of_grad": ("Foreign-born share of graduate-degree holders, 25+ (ACS)", PCT, F_PCT),
    }
    p = pd.read_csv(DATA / "acs" / "pums_stem.csv")
    p = p[p.group == "all"]
    # shares resting on fewer than MIN_N sample records are left blank
    MIN_N = 100
    p.loc[(p.measure != "stem_workers") & (p.measure != "stem_share_of_workers") & (p.n < MIN_N), "value"] = None
    p = p.assign(measure="acs_" + p.measure, value=p.value.where(p.measure.isin(["stem_workers"]), p.value * 100))
    t = pd.read_csv(DATA / "acs" / "table_measures.csv").assign(value=lambda d: d.value * 100)
    t = t[t.measure.isin(["acs_fb_share", "acs_fb_share_of_grad"])]
    d = pd.concat([p[["state", "year", "measure", "value"]], t[["state", "year", "measure", "value"]]])
    base = ("U.S. Census Bureau, American Community Survey 1-year (no 2020: the Bureau released only experimental "
            "1-year data). ")
    pums = (base + "Microdata (PUMS): employed workers in STEM occupations (SOC 15, 17, 19 and the STEM manager codes "
            "11-3021, 11-9041, 11-9121), counted where they live. Shares resting on fewer than 100 sample records "
            "are blank (small states, and the country and doctorate measures in many states). Part of the rise in "
            "STEM workers comes from the 2018 occupation-code revision. Microdata run through 2024 (the 2025 1-year PUMS "
            "was not yet released as of November 2026).")
    notes = {k: pums for k in m}
    notes["acs_stem_noncit_share"] += " Noncitizens include green-card holders and temporary-visa workers; the ACS does not separate them."
    tabs = base + "Published detailed tables B05002 and B06009, 2014-2025."
    notes["acs_fb_share"] = notes["acs_fb_share_of_grad"] = tabs
    return d, m, notes


def naep():
    w = pd.read_csv(DATA / "naep" / "naep_wide.csv")
    w = w[w.jurisdiction.ne("NT")]                    # states are public schools; US = national public (NP)
    w["state"] = w.state.replace({"US public": "US"})
    # one value per year: the accommodations-permitted sample (R3) where both exist
    w = w.sort_values("sample").drop_duplicates(["state", "subject", "grade", "scale", "year"], keep="last")
    spec = [  # (subject, grade, scale, stat, name, title, unit, fmt)
        ("MAT", 8, "MRPCM", "mean", "naep_math8", "Grade 8 mathematics, average score (NAEP)", "score", F_SCORE),
        ("MAT", 8, "MRPCM", "at_or_above_proficient", "naep_math8_prof", "Grade 8 mathematics: at or above Proficient (NAEP)", PCT, F_PCT),
        ("MAT", 8, "MRPCM", "advanced", "naep_math8_adv", "Grade 8 mathematics: at Advanced (NAEP)", PCT, F_PCT),
        ("MAT", 8, "MRPCM", "p90", "naep_math8_p90", "Grade 8 mathematics, 90th percentile score (NAEP)", "score", F_SCORE),
        ("MAT", 4, "MRPCM", "mean", "naep_math4", "Grade 4 mathematics, average score (NAEP)", "score", F_SCORE),
        ("MAT", 4, "MRPCM", "at_or_above_proficient", "naep_math4_prof", "Grade 4 mathematics: at or above Proficient (NAEP)", PCT, F_PCT),
        ("RED", 8, "RRPCM", "mean", "naep_read8", "Grade 8 reading, average score (NAEP)", "score", F_SCORE),
        ("RED", 8, "RRPCM", "at_or_above_proficient", "naep_read8_prof", "Grade 8 reading: at or above Proficient (NAEP)", PCT, F_PCT),
        ("RED", 4, "RRPCM", "mean", "naep_read4", "Grade 4 reading, average score (NAEP)", "score", F_SCORE),
        ("SCI", 8, "SRPUV", "mean", "naep_sci8", "Grade 8 science, average score, 2009 framework (NAEP)", "score", F_SCORE),
    ]
    rows, m = [], {}
    for subj, g, scale, stat, name, title, unit, f in spec:
        x = w[(w.subject == subj) & (w.grade == g) & (w.scale == scale)]
        rows.append(pd.DataFrame({"state": x.state, "year": x.year, "measure": name, "value": x[stat]}))
        m[name] = (title, unit, f)
    note = ("NCES, NAEP (The Nation's Report Card), main assessments, all students in public schools; U.S. = national "
            "public. Years with both samples use the accommodations-permitted one. Scores are on NAEP's 0-500 scale; "
            "a difference of a few points may not be statistically significant (standard errors are in "
            "data/naep/naep_wide.csv). All subjects, grades, subscales and statistics are in data/naep/.")
    return pd.concat(rows).dropna(subset=["value"]), m, {k: note for k in m}


def gss():
    w = pd.read_csv(DATA / "gss" / "gss_state_wide.csv")
    cols = {"grad_total__all_se": "gss_grad_se", "grad_temp_visa__all_se": "gss_grad_se_tv",
            "grad_temp_visa_share__all_se": "gss_grad_se_tv_share", "grad_temp_visa_share__engineering": "gss_grad_eng_tv_share",
            "postdoc_total__all_se": "gss_postdoc_se", "postdoc_temp_visa_share__all_se": "gss_postdoc_se_tv_share"}
    d = _long(w, "survey_year", cols)                 # GSS shares are already 0-100
    m = {"gss_grad_se": ("Graduate students in science & engineering (NSF GSS)", "students", F_N),
         "gss_grad_se_tv": ("S&E graduate students on temporary visas (NSF GSS)", "students", F_N),
         "gss_grad_se_tv_share": ("Temporary-visa share of S&E graduate students (NSF GSS)", PCT, F_PCT),
         "gss_grad_eng_tv_share": ("Temporary-visa share of engineering graduate students (NSF GSS)", PCT, F_PCT),
         "gss_postdoc_se": ("S&E postdoctoral appointees (NSF GSS)", "postdocs", F_N),
         "gss_postdoc_se_tv_share": ("Temporary-visa share of S&E postdocs (NSF GSS)", PCT, F_PCT)}
    note = ("NSF NCSES, Survey of Graduate Students and Postdoctorates in S&E, counted at the institution's state "
            "(fall survey year). NSF published state tables for 1994 and 1996-2016 (postdocs 2010-2016); from 2017 "
            "only national figures exist, so the state series end in 2016. Breaks: 2007 field reclassification, "
            "2014 frame expansion. Science includes psychology and the social sciences; health is excluded.")
    return d, m, {k: note for k in m}


def sed():
    w = pd.read_csv(DATA / "sed" / "sed_state_wide.csv").copy()
    us = w[w.state == "US"].set_index("year")
    w["share_of_us"] = w.doctorates__all / w.year.map(us.doctorates__all)
    w["se_share"] = w.doctorates__se_excl_health / w.doctorates__all
    cols = {"doctorates__all": "sed_doctorates", "doctorates__se_excl_health": "sed_doctorates_se", "share_of_us": "sed_share_of_us",
            "se_share": "sed_se_share", "doctorates__engineering": "sed_doctorates_eng", "doctorates__math_cs": "sed_doctorates_mathcs"}
    m = {"sed_doctorates": ("Research doctorates awarded (NSF SED)", "doctorates", F_N),
         "sed_doctorates_se": ("Science & engineering research doctorates, excluding health (NSF SED)", "doctorates", F_N),
         "sed_share_of_us": ("Share of U.S. research doctorates (NSF SED)", PCT, F_PCT),
         "sed_se_share": ("S&E share of the state's research doctorates, excluding health (NSF SED)", PCT, F_PCT),
         "sed_doctorates_eng": ("Engineering research doctorates (NSF SED)", "doctorates", F_N),
         "sed_doctorates_mathcs": ("Mathematics & computer science research doctorates (NSF SED)", "doctorates", F_N)}
    last = us.dropna(subset=["doctorates_temp_visa_share__se"]).index.max()
    ctx = ""
    if pd.notna(last):
        r = us.loc[last]
        tv = r.get("doctorates_temp_visa_share__se")
        sr = r.get("stay_rate_temp_visa__all") if "stay_rate_temp_visa__all" in us else None
        ctx = (f" Citizenship is published only for the nation: in {int(last)}, {tv:.1f}% of U.S. S&E doctorates went to "
               f"temporary-visa holders" + (f", and {sr:.0f}% of those with definite plans were staying in the U.S." if sr is not None and pd.notna(sr) else "."))
    note = ("NSF NCSES, Survey of Earned Doctorates: research doctorates by the state of the doctorate-granting institution "
            "and academic year of the award. S&E excludes health so that years before and "
            "after the 2009 reclassification compare; the 2021 field taxonomy changed again. NSF publishes no state "
            "breakdown by citizenship or postgraduation plans." + ctx)
    return _long(w, "year", cols, {"share_of_us", "se_share"}), m, {k: note for k in m}


def h1b():
    w = pd.read_csv(DATA / "h1b" / "h1b_state_wide.csv")
    w = w[~w.incomplete_export]
    us = w[w.state == "US"].set_index("fiscal_year").initial_approved
    w["share_of_us"] = w.initial_approved / w.fiscal_year.map(us)
    cols = {"initial_approved": "h1b_initial", "continuing_approved": "h1b_continuing", "share_of_us": "h1b_initial_share_of_us",
            "initial_denial_rate": "h1b_initial_denial_rate", "initial_share_education": "h1b_initial_share_education",
            "initial_share_prof_sci_tech": "h1b_initial_share_profsci", "initial_share_top5_employers": "h1b_initial_share_top5"}
    pct = {"share_of_us", "initial_denial_rate", "initial_share_education", "initial_share_prof_sci_tech", "initial_share_top5_employers"}
    m = {"h1b_initial": ("New H-1B approvals (initial), by employer state (USCIS)", "petitions", F_N),
         "h1b_continuing": ("Continuing H-1B approvals, by employer state (USCIS)", "petitions", F_N),
         "h1b_initial_share_of_us": ("Share of U.S. new H-1B approvals (USCIS)", PCT, F_PCT),
         "h1b_initial_denial_rate": ("Denial rate, new H-1B petitions (USCIS)", PCT, F_PCT),
         "h1b_initial_share_education": ("New H-1B approvals at colleges and schools (NAICS 61) (USCIS)", PCT, F_PCT),
         "h1b_initial_share_profsci": ("New H-1B approvals in professional, scientific & technical services (USCIS)", PCT, F_PCT),
         "h1b_initial_share_top5": ("Five largest employers' share of new H-1B approvals (USCIS)", PCT, F_PCT)}
    note = ("USCIS, H-1B Employer Data Hub, by fiscal year of the first decision. State is the petitioning employer's "
            "address, often headquarters, not the worksite (Amazon files from Virginia); DOL's LCA rows give the "
            "worksite. Initial = new employment and new concurrent employment; continuing = extensions, changes of "
            "employer and amendments (USCIS's definitions). Every year is exported from the current Data Hub tool, so "
            "FY2009-2026 are on one method; FY2016-2025 match USCIS's Characteristics of H-1B reports to within 0.2%.")
    return _long(w, "fiscal_year", cols, pct), m, {k: note for k in m}


def dol():
    l = pd.read_csv(DATA / "dol" / "lca_state_wide.csv")
    p = pd.read_csv(DATA / "dol" / "perm_state_wide.csv")
    l, p = l[l.partial == 0], p[p.partial == 0]
    us = l[l.state == "US"].set_index("fiscal_year").h1b_positions
    l["share_of_us"] = l.h1b_positions / l.fiscal_year.map(us)
    lc = {"h1b_positions": "dol_h1b_positions", "share_of_us": "dol_h1b_share_of_us", "h1b_stem_share": "dol_h1b_stem_share",
          "h1b_median_wage": "dol_h1b_median_wage", "h1b_dependent_share": "dol_h1b_dependent_share"}
    pc = {"perm_cert": "dol_perm_cert", "perm_india_share": "dol_perm_india_share", "perm_adm_f1_share": "dol_perm_f1_share",
          "perm_fw_grad_share": "dol_perm_grad_share", "perm_stem_share": "dol_perm_stem_share", "perm_median_wage": "dol_perm_median_wage"}
    d = pd.concat([_long(l, "fiscal_year", lc, {"share_of_us", "h1b_stem_share", "h1b_dependent_share"}),
                   _long(p, "fiscal_year", pc, {"perm_india_share", "perm_adm_f1_share", "perm_fw_grad_share", "perm_stem_share"})])
    m = {"dol_h1b_positions": ("Certified H-1B positions, by worksite (DOL LCA)", "positions", F_N),
         "dol_h1b_share_of_us": ("Share of U.S. certified H-1B positions (DOL LCA)", PCT, F_PCT),
         "dol_h1b_stem_share": ("STEM share of certified H-1B positions (DOL LCA)", PCT, F_PCT),
         "dol_h1b_median_wage": ("Median offered H-1B wage, nominal dollars (DOL LCA)", USD, F_USD),
         "dol_h1b_dependent_share": ("H-1B positions at H-1B-dependent employers (DOL LCA)", PCT, F_PCT),
         "dol_perm_cert": ("Green-card labor certifications (DOL PERM)", "certifications", F_N),
         "dol_perm_india_share": ("Share of PERM certifications for citizens of India (DOL)", PCT, F_PCT),
         "dol_perm_f1_share": ("PERM certifications for workers on F-1 student visas (DOL)", PCT, F_PCT),
         "dol_perm_grad_share": ("PERM workers with a master's or doctorate (DOL)", PCT, F_PCT),
         "dol_perm_stem_share": ("STEM share of PERM certifications (DOL)", PCT, F_PCT),
         "dol_perm_median_wage": ("Median offered PERM wage, nominal dollars (DOL)", USD, F_USD)}
    lca = ("DOL Office of Foreign Labor Certification, LCA disclosure data, by fiscal year and the first worksite's "
           "state. An LCA comes before an H-1B petition, so certified positions overstate hires (some are never "
           "filed or selected). Certified = CERTIFIED plus CERTIFIED-WITHDRAWN. STEM occupations = SOC 15, 17, 19 "
           "and STEM managers. FY2026 (partial) is left out. Wages are not adjusted for inflation.")
    perm = ("DOL Office of Foreign Labor Certification, PERM disclosure data, by fiscal year and worksite state: the "
            "employer's labor certification for an employment-based green card. Certified = CERTIFIED plus "
            "CERTIFIED-EXPIRED. Citizenship, class of admission and education are not on the form DOL uses from "
            "FY2025, so those series end in FY2024. FY2026 (partial) is left out.")
    return d, m, {k: (lca if "h1b" in k else perm) for k in m}


def patents():
    w = pd.read_csv(DATA / "patents" / "patents_state_wide.csv")
    cols = {"patents_frac": "pat_patents", "share_of_us_frac": "pat_share_of_us", "share_digital": "pat_share_digital",
            "share_life_sciences": "pat_share_life", "share_semiconductors": "pat_share_semis",
            "women_share_of_inventors": "pat_women_share"}
    pct = {"share_of_us_frac", "share_digital", "share_life_sciences", "share_semiconductors", "women_share_of_inventors"}
    m = {"pat_patents": ("Patents granted to assignees in the state (USPTO)", "patents", F_N),
         "pat_share_of_us": ("Share of U.S.-assignee patents (USPTO)", PCT, F_PCT),
         "pat_share_digital": ("Share of the state's patents in digital technologies (USPTO)", PCT, F_PCT),
         "pat_share_life": ("Share of the state's patents in life sciences (USPTO)", PCT, F_PCT),
         "pat_share_semis": ("Share of the state's patents in semiconductors (USPTO)", PCT, F_PCT),
         "pat_women_share": ("Women's share of inventors on the state's patents (USPTO)", PCT, F_PCT)}
    note = ("USPTO via PatentsView annualized files, by grant year and the state of the patent's owner (assignee), "
            "fractionally counted across co-owners; not where inventors live. Unassigned patents (about 5%) have no "
            "location. Technology groups use the WIPO "
            "field of the patent's first classification.")
    return _long(w, "grant_year", cols, pct), m, {k: note for k in m}


def migration():
    w = pd.read_csv(DATA / "acs_migration" / "migration_state_wide.csv")
    cols = {"net_ba_plus_per_1000": "mig_net_ba_plus_per_1000", "net_ba_plus": "mig_net_ba_plus", "net_grad": "mig_net_grad",
            "in_rate_ba_plus": "mig_in_rate_ba_plus", "out_rate_ba_plus": "mig_out_rate_ba_plus", "abroad_ba_plus": "mig_abroad_ba_plus"}
    m = {"mig_net_ba_plus_per_1000": ("Net domestic migration of bachelor's-plus adults, per 1,000 residents (ACS)", "per 1,000", "{:+.1f}"),
         "mig_net_ba_plus": ("Net domestic migration of bachelor's-plus adults (ACS)", "adults", "{:+,.0f}"),
         "mig_net_grad": ("Net domestic migration of graduate-degree holders (ACS)", "adults", "{:+,.0f}"),
         "mig_in_rate_ba_plus": ("Bachelor's-plus adults who moved in from another state (ACS)", PCT, "{:.2f}%"),
         "mig_out_rate_ba_plus": ("Bachelor's-plus adults who moved out to another state (ACS)", PCT, "{:.2f}%"),
         "mig_abroad_ba_plus": ("Bachelor's-plus adults who arrived from abroad in the past year (ACS)", "adults", F_N)}
    note = ("U.S. Census Bureau, ACS 1-year tables B07009 (residence now) and B07409 (residence a year ago), adults 25+. Net = "
            "movers in from other states minus movers out to other states in the past year; the U.S. has no net. Arrivals from "
            "abroad have no outflow counterpart in the ACS. No 2020. Small states' net flows are often within the margin of error "
            "(data/acs_migration/migration_long.csv).")
    return _long(w, "year", cols), m, {k: note for k in m}


def scorecard():
    w = pd.read_csv(DATA / "scorecard" / "scorecard_state_wide.csv")
    w["year"] = 2025
    latest = {"inst_earn1_median": "sc_earn1", "prog_earn1_bach_stem": "sc_earn1_bach_stem",
              "prog_earn1_bach_nonstem": "sc_earn1_bach_nonstem", "prog_stem_premium1_bach": "sc_stem_premium_bach",
              "prog_earn5_bach_all": "sc_earn5_bach", "prog_earn1_master_stem": "sc_earn1_master_stem"}
    # year-keyed institution measures: year = the API's data-file year (MERGED<year>_<year+1>); labels say what it measures
    h = pd.read_csv(DATA / "scorecard" / "scorecard_state_years.csv")
    hist = {"inst_earn10_median": "sc_earn10", "inst_debt_median": "sc_debt", "inst_completion_4yr": "sc_completion_4yr",
            "inst_pell_share": "sc_pell_share", "inst_ugds": "sc_ugds"}
    h.loc[h.year < 2020, "inst_earn10_median"] = None    # 2007-2014 files cover about half the students: not comparable
    d = pd.concat([_long(w, "year", latest), _long(h, "year", hist)])
    m = {"sc_earn10": ("Median earnings 10 years after entering college (College Scorecard)", "2024 $", F_USD),
         "sc_earn1": ("Median earnings 1 year after completing (College Scorecard)", "2024 $", F_USD),
         "sc_debt": ("Median debt of completers (College Scorecard)", "nominal $", F_USD),
         "sc_completion_4yr": ("Completion rate at 4-year institutions, 150% time (College Scorecard)", PCT, F_PCT),
         "sc_pell_share": ("Pell Grant share of undergraduates (College Scorecard)", PCT, F_PCT),
         "sc_ugds": ("Undergraduate degree-seeking enrollment, Title IV institutions (College Scorecard)", "students", F_N),
         "sc_earn1_bach_stem": ("STEM bachelor's graduates: median earnings 1 year out (College Scorecard)", "2024 $", F_USD),
         "sc_earn1_bach_nonstem": ("Non-STEM bachelor's graduates: median earnings 1 year out (College Scorecard)", "2024 $", F_USD),
         "sc_stem_premium_bach": ("STEM earnings premium for bachelor's graduates, 1 year out (College Scorecard)", "2024 $", "${:+,.0f}"),
         "sc_earn5_bach": ("Bachelor's graduates: median earnings 5 years out (College Scorecard)", "2024 $", F_USD),
         "sc_earn1_master_stem": ("STEM master's graduates: median earnings 1 year out (College Scorecard)", "2024 $", F_USD)}
    for k in latest.values():
        MONTHS[k] = {2025: "latest release"}
    ys = sorted(int(y) for y in h.year.unique())
    yy = lambda y: f"{y}–{str(y + 1)[-2:]}"          # noqa: E731
    MONTHS["sc_earn10"] = {y: f"earned {yy(y)}" for y in ys}              # entrants AY(y-11)-(y-9), measured CY y, y+1
    MONTHS["sc_debt"] = {y: f"FY{yy(y)} completers" for y in ys}          # NSLDS FY y and y+1 pooled
    MONTHS["sc_completion_4yr"] = {y: f"fall {y - 6} entrants" for y in ys}
    MONTHS["sc_pell_share"] = {y: yy(y - 1) for y in ys}                  # academic year y-1 to y
    MONTHS["sc_ugds"] = {y: f"fall {y}" for y in ys}
    base = ("U.S. Department of Education, College Scorecard API, institutions located in the state that are in the current "
            "Scorecard file (closed institutions are not served, so early years undercount). State values are medians of "
            "institution or program medians weighted by students measured (earnings) or undergraduate enrollment (debt, "
            "completion, Pell). ")
    one = " Latest release only (no trend)."
    notes = {k: base + "Earnings are for federal-aid recipients working and not enrolled (Treasury records), in 2024 dollars; "
             "completers AY2020-22, measured 1 (or 5) years after completion. STEM = CIP 03, 04, 11, 14, 15, 26, 27, 40." + one
             for k in latest.values()}
    notes["sc_earn10"] = base + ("Median earnings of federal-aid recipients working and not enrolled 10 years after entering "
                                 "(Treasury), pooled two-year entry cohorts measured in the calendar years shown (2022-23: "
                                 "entrants AY2011-13); converted to 2024 dollars with the CPI-U. Shown for the 2020 and 2022 "
                                 "data files; the 2007-2014 files count about half as many students and weight large online "
                                 "institutions less, so they are not comparable and are left out (they are in "
                                 "data/scorecard/scorecard_state_years.csv).")
    notes["sc_debt"] = base + ("Median federal loan debt of completers (NSLDS), the two fiscal years of repayment entry shown "
                               "pooled; nominal dollars.")
    notes["sc_completion_4yr"] = base + ("First-time, full-time students completing within 150% of normal time at 4-year "
                                         "institutions (IPEDS), by entering cohort.")
    notes["sc_pell_share"] = base + "Share of undergraduates receiving a Pell Grant (IPEDS), by academic year."
    notes["sc_ugds"] = base + ("Sum of undergraduate certificate- and degree-seeking enrollment, fall (IPEDS), Title IV "
                               "institutions only.")
    return d, m, notes


def k12():
    w = pd.read_csv(DATA / "digest_k12" / "k12_state_wide.csv")
    w.loc[w.year < 2011, "k12_el_pct"] = None     # before 2010-11 older editions count students in EL programs, not identified ELs
    m = {"k12_ppe": ("Current spending per public-school pupil (NCES)", "2024 $", F_USD),
         "k12_acgr": ("Public high school 4-year graduation rate, ACGR (NCES)", PCT, F_PCT),
         "k12_afgr": ("Public high school averaged freshman graduation rate (NCES)", PCT, F_PCT),
         "k12_hs_grads": ("Public high school graduates (NCES)", "graduates", F_N),
         "k12_teacher_salary": ("Average public-school teacher salary (NCES)", "2024 $", F_USD),
         "k12_pupil_teacher": ("Pupils per teacher, public schools (NCES)", "ratio", "{:.1f}"),
         "k12_enroll": ("Public elementary and secondary enrollment (NCES)", "students", F_N),
         "k12_frpl_pct": ("Public-school students eligible for free or reduced-price lunch (NCES)", PCT, F_PCT),
         "k12_el_pct": ("English learners as a share of public-school students (NCES)", PCT, F_PCT),
         "k12_charter_enroll_pct": ("Charter-school share of public-school enrollment (NCES)", PCT, F_PCT)}
    fall = {"k12_enroll", "k12_pupil_teacher"}     # fall counts keep the fall year; the rest are school years (spring)
    for k in m:
        MONTHS[k] = {int(y): (f"Fall {int(y)}" if k in fall else f"{int(y) - 1}-{str(int(y))[-2:]}")
                     for y in w.dropna(subset=[k]).year.unique()} if k in w else {}
    base = ("NCES, Digest of Education Statistics, every edition 1995-2025 (Common Core of Data, EDFacts); for each "
            "state and year the latest edition that prints it. Years are school years. ")
    usd = " Dollars deflated to 2024 dollars with the CPI-U (academic-year average)."
    notes = {
        "k12_ppe": base + "Table 236.65 (older editions' equivalents): current expenditures per pupil in fall enrollment." + usd,
        "k12_acgr": base + "Table 219.46, 2010-11 on. The Digest prints 2019-20 and 2020-21 only by student group, so "
                           "those years are blank.",
        "k12_afgr": base + "Tables 219.35, 219.40-219.41: graduates with a regular diploma divided by the average of "
                           "8th-grade enrollment 5 years earlier, 9th-grade 4 years earlier and 10th-grade 3 years earlier.",
        "k12_hs_grads": base + "Table 219.20: public high school graduates with a regular diploma (no GEDs).",
        "k12_teacher_salary": base + "Table 211.60 (National Education Association estimates)." + usd,
        "k12_pupil_teacher": base + "Table 208.40: fall enrollment divided by full-time-equivalent teachers. Fall of the school year.",
        "k12_enroll": base + "Table 203.20: fall enrollment, prekindergarten through grade 12. Fall of the school year.",
        "k12_frpl_pct": base + "Table 204.10. Community eligibility (2014-15 on) lets high-poverty schools count every "
                               "student, which raises the share in some states (Mississippi, D.C.).",
        "k12_el_pct": base + "Table 204.20: English learners identified in the fall, 2010-11 on (older editions count "
                             "students in English-learner programs, a different concept, and are left out; they are in "
                             "data/digest_k12/).",
        "k12_charter_enroll_pct": base + "Table 216.90: fall enrollment in public charter schools as a share of all "
                                         "public-school enrollment.",
    }
    return _long(w, "year", {k: k for k in m}), m, notes


def digest_ps():
    w = pd.read_csv(DATA / "digest_state" / "postsec_state_wide.csv")
    m = {"fresh_leave_share_hs": ("Recent high school graduates who go to college out of state (NCES)", PCT, F_PCT),
         "fresh_leave_share_4yr": ("Recent high school graduates in 4-year colleges who go out of state (NCES)", PCT, F_PCT)}
    for k in m:
        MONTHS[k] = {int(y): f"Fall {int(y)}" for y in w.dropna(subset=[k]).year.unique()}
    note = ("NCES, Digest of Education Statistics tables 309.20 and 309.30 (and older editions' equivalents), from the "
            "IPEDS fall enrollment residence data (every other fall until 2008): first-time students who graduated from "
            "high school in the previous 12 months, by state of residence. Share = residents enrolled in another state / "
            "residents enrolled in any state. All counts (residents, stayers, in- and out-migrants) are in "
            "data/digest_state/.")
    return _long(w, "year", {k: k for k in m}), m, {k: note for k in m}


def opt():
    w = pd.read_csv(DATA / "ice_foia" / "opt_state_wide.csv")
    emp = w[(w.opt_partial_year == 0) & (w.opt_emp_state_reliable == 1)].copy()
    stem = w[w.stem_opt_partial_year == 0].copy()
    d = pd.concat([_long(emp, "year", {"opt_retention": "opt_retention", "opt_retention__bach": "opt_retention_bach",
                                       "opt_retention__master": "opt_retention_master", "opt_retention__stem": "opt_retention_stem",
                                       "opt_employer_to_school": "opt_employer_to_school"},
                         {"opt_retention", "opt_retention__bach", "opt_retention__master", "opt_retention__stem"}),
                   _long(stem, "year", {"stem_opt_approved": "opt_stem_approved"})])
    m = {"opt_retention": ("International graduates on OPT working in the state where they studied (ICE)", PCT, F_PCT),
         "opt_retention_bach": ("OPT retention, bachelor's graduates (ICE)", PCT, F_PCT),
         "opt_retention_master": ("OPT retention, master's graduates (ICE)", PCT, F_PCT),
         "opt_retention_stem": ("OPT retention, STEM graduates (ICE)", PCT, F_PCT),
         "opt_employer_to_school": ("OPT workers employed in the state per OPT graduate of its schools (ICE)", "ratio", "{:.2f}"),
         "opt_stem_approved": ("STEM OPT extensions approved, by state of the school (ICE)", "approvals", F_N)}
    note = ("ICE, SEVIS FOIA releases of Optional Practical Training records. Retention = OPT employment records at employers in "
            "the school's state, of records with a known employer state; ratio = OPT starts at employers in the state per "
            "known-employer start from its schools (above 1: the state draws in more OPT workers than its colleges send out). "
            "The OPT file was cut off at Excel's 1,048,575-row limit, so counts are lower bounds and only shares are shown; "
            "employer state is mostly missing before 2008, and 2017 is partial. STEM OPT extensions are complete but carry no "
            "location, so they are counted by the school's state. Records are employment spells, not students.")
    return d, m, {k: note for k in m}


def j1():
    w = pd.read_csv(DATA / "j1" / "j1_state_wide.csv")
    long = w.melt(id_vars=["state"], value_vars=[c for c in w if c.startswith("participants_")], var_name="y", value_name="value")
    long = long.assign(year=long.y.str[-4:].astype(int), measure="j1_participants")[["state", "year", "measure", "value"]].dropna()
    m = {"j1_participants": ("J-1 exchange visitors starting a program in the state (State Dept.)", "participants", F_N)}
    note = ("U.S. Department of State, BridgeUSA, J-1 participants by site-of-activity state and program begin year. All "
            "categories together (the state table has no category split), so most are Summer Work Travel, camp counselors and "
            "au pairs, not only students and scholars. 2020 reflects the pandemic; 2025 may be incomplete.")
    return long, m, {k: note for k in m}


def pseo():
    w = pd.read_csv(DATA / "pseo" / "pseo_state_wide.csv")
    w = w[pd.to_numeric(w.grad_cohort, errors="coerce").notna()].copy()     # drop the all-cohort rollup rows
    w["grad_cohort"] = w.grad_cohort.astype(float).astype(int)
    w["cohort_years"] = pd.to_numeric(w.cohort_years, errors="coerce").fillna(1).astype(int)
    w["earn"] = w.p50_earnings.fillna(w.p50_earnings_wmean)
    spec = [  # (name, degree, field, years after, column, title, unit, fmt)
        ("pseo_instate_bach_y1", "bach", "all", 1, "share_instate", "Bachelor's graduates working in the state 1 year after graduating (PSEO)", PCT, F_PCT),
        ("pseo_instate_bach_y5", "bach", "all", 5, "share_instate", "Bachelor's graduates working in the state 5 years after graduating (PSEO)", PCT, F_PCT),
        ("pseo_instate_bach_y10", "bach", "all", 10, "share_instate", "Bachelor's graduates working in the state 10 years after graduating (PSEO)", PCT, F_PCT),
        ("pseo_instate_bach_stem_y1", "bach", "stem", 1, "share_instate", "STEM bachelor's graduates working in the state 1 year out (PSEO)", PCT, F_PCT),
        ("pseo_instate_master_y1", "master", "all", 1, "share_instate", "Master's graduates working in the state 1 year out (PSEO)", PCT, F_PCT),
        ("pseo_instate_doc_y1", "doctoral", "all", 1, "share_instate", "Doctoral graduates working in the state 1 year out (PSEO)", PCT, F_PCT),
        ("pseo_earn_bach_y1", "bach", "all", 1, "earn", "Bachelor's graduates' median earnings 1 year out (PSEO)", "$", F_USD),
        ("pseo_earn_bach_y5", "bach", "all", 5, "earn", "Bachelor's graduates' median earnings 5 years out (PSEO)", "$", F_USD),
        ("pseo_earn_bach_stem_y1", "bach", "stem", 1, "earn", "STEM bachelor's graduates' median earnings 1 year out (PSEO)", "$", F_USD),
    ]
    rows, m = [], {}
    for name, deg, fld, ya, col, title, unit, f in spec:
        x = w[(w.degree_level == deg) & (w.field == fld) & (w.years_after == ya)]
        v = x[col] * (100 if col == "share_instate" else 1)
        rows.append(pd.DataFrame({"state": x.state, "year": x.grad_cohort.astype(int), "measure": name, "value": v}))
        m[name] = (title, unit, f)
        MONTHS[name] = {int(y): f"{int(y)}–{str(int(y) + int(c) - 1)[-2:]} grads" for y, c in zip(x.grad_cohort, x.cohort_years)}
    note = ("U.S. Census Bureau, Post-Secondary Employment Outcomes (latest release, R2026Q2), statewide rows: graduates of the "
            "participating institutions in the state (37 states and DC; coverage of the state's bachelor's degrees ranges from "
            "near full in MD, NM, VA, SC, NJ, IN and TX to partial in NY, MA, PA, MI, DC; U.S. = all participating states). Share = graduates employed in the "
            "institution's state, of all employed graduates, by graduating cohort (bachelor's: 3-year cohorts; others: 5-year), "
            "measured 1, 5 or 10 years after graduation. PSEO reports only in-state vs Census division, not destination states. "
            "Earnings are Census's inflation-adjusted medians; STEM and doctoral rows are graduate-weighted means of published "
            "medians. Suppressed cells are blank.")
    return pd.concat(rows).dropna(subset=["value"]), m, {k: note for k in m}


def oews():
    w = pd.read_csv(DATA / "oews" / "oews_state_wide.csv")
    cols = {"stem_emp": "oews_stem_emp", "stem_share": "oews_stem_share", "stem_lq": "oews_stem_lq", "stem_a_mean": "oews_stem_wage",
            "stem_a_median_approx": "oews_stem_median", "a_median_software_dev": "oews_softdev_median", "emp_software_dev": "oews_softdev_emp",
            "a_mean_total": "oews_all_wage"}
    m = {"oews_stem_emp": ("STEM jobs, employer survey (BLS OEWS)", "jobs", F_N),
         "oews_stem_share": ("STEM share of all jobs (BLS OEWS)", PCT, "{:.2f}%"),
         "oews_stem_lq": ("STEM jobs concentration vs the U.S., location quotient (BLS OEWS)", "ratio", "{:.2f}"),
         "oews_stem_wage": ("Mean annual STEM wage, nominal (BLS OEWS)", "nominal $", F_USD),
         "oews_stem_median": ("Median annual STEM wage, nominal, approximate (BLS OEWS)", "nominal $", F_USD),
         "oews_softdev_median": ("Median software developer wage, nominal (BLS OEWS)", "nominal $", F_USD),
         "oews_softdev_emp": ("Software developer jobs (BLS OEWS)", "jobs", F_N),
         "oews_all_wage": ("Mean annual wage, all occupations, nominal (BLS OEWS)", "nominal $", F_USD)}
    note = ("BLS Occupational Employment and Wage Statistics, May estimates (1999-2001 annual, 2002 November), jobs at employers "
            "located in the state. STEM = SOC 15, 17, 19 and the three STEM manager codes, as in the ACS and DOL rows; unlike the "
            "ACS it counts jobs where they are, not workers where they live, and excludes the self-employed. SOC vintages change "
            "in 2010, 2012, 2019 and 2021; software developers include QA analysts in 2019-20. The STEM median is an "
            "employment-weighted median of occupation medians. Wages are not adjusted for inflation.")
    return _long(w, "year", cols, {"stem_share"}), m, {k: note for k in m}


def crdc():
    w = pd.read_csv(DATA / "crdc" / "crdc_state_wide.csv")
    w = w[w.year != 2010]          # 2009-10: an unweighted district sample (shares and rates run high); kept in the CSVs only
    share = {"share_hs_offer_calc": "crdc_calc", "share_hs_offer_phys": "crdc_phys", "share_hs_offer_chem": "crdc_chem",
             "share_hs_offer_alg2": "crdc_alg2", "share_hs_offer_csci": "crdc_csci", "share_hs_offer_ap": "crdc_ap",
             "share_hs_offer_apcs": "crdc_apcs", "share_hs_offer_dual": "crdc_dual"}
    rate = {"enr_ap_per100": "crdc_ap_per100", "enr_calc_per100": "crdc_calc_per100",
            "enr_phys_per100": "crdc_phys_per100", "enr_satact_per100": "crdc_satact_per100",
            "enr_gt_per100_all": "crdc_gt_per100"}
    d = pd.concat([_long(w, "year", share, set(share)), _long(w, "year", rate)])
    m = {"crdc_calc": ("High schools offering calculus (CRDC)", PCT, F_PCT),
         "crdc_phys": ("High schools offering physics (CRDC)", PCT, F_PCT),
         "crdc_chem": ("High schools offering chemistry (CRDC)", PCT, F_PCT),
         "crdc_alg2": ("High schools offering Algebra II (CRDC)", PCT, F_PCT),
         "crdc_csci": ("High schools offering computer science (CRDC)", PCT, F_PCT),
         "crdc_ap": ("High schools offering any AP course (CRDC)", PCT, F_PCT),
         "crdc_apcs": ("High schools offering AP computer science (CRDC)", PCT, F_PCT),
         "crdc_dual": ("High schools offering dual enrollment (CRDC)", PCT, F_PCT),
         "crdc_ap_per100": ("AP course enrollments per 100 high-school students (CRDC)", "per 100", "{:.1f}"),
         "crdc_calc_per100": ("Calculus enrollments per 100 high-school students (CRDC)", "per 100", "{:.1f}"),
         "crdc_phys_per100": ("Physics enrollments per 100 high-school students (CRDC)", "per 100", "{:.1f}"),
         "crdc_satact_per100": ("SAT or ACT takers per 100 high-school students (CRDC)", "per 100", "{:.1f}"),
         "crdc_gt_per100": ("Students in gifted and talented programs per 100 students (CRDC)", "per 100", "{:.1f}")}
    for k in m:   # year = spring of the school year
        MONTHS[k] = {int(y): f"{int(y) - 1}-{str(int(y))[-2:]}" for y in w.year.unique()}
    note = ("U.S. Department of Education, Office for Civil Rights, Civil Rights Data Collection, school years "
            "2011-12, 2013-14, 2015-16, 2017-18, 2020-21, 2021-22 and 2023-24 (school-level files). High school = public "
            "school enrolling students in each of grades 10-12, excluding justice facilities. A course is offered when the "
            "school reports at least one class. 2009-10 was an unweighted sample of districts and is left out here (it is in "
            "data/crdc/). "
            "Computer science is collected from 2020-21, dual enrollment from 2013-14. Reserve codes are treated as missing; "
            "public-use counts are perturbed for privacy. AP math includes AP Precalculus from 2023-24.")
    notes = {k: note for k in m}
    notes["crdc_gt_per100"] = (
        "Students in gifted and talented programs per 100 students enrolled, all public schools and grades. 2009-10 "
        "onward from the school-level files (2009-10: sampled schools); 2000-01, 2004-05 and 2006-07 from OCR's "
        "published state projections; 1980-81 and 1990-91 from OCR's CRDC archive district files (weighted sums). "
        "Earlier surveys were samples of districts, so year-to-year changes in small states partly reflect the sample. "
        "U.S. Department of Education, Office for Civil Rights, Civil Rights Data Collection.")
    notes["crdc_satact_per100"] = note + " SAT/ACT takers are students in grades 11-12 who took either test during the year."
    return d, m, notes


def dhs():
    w = pd.read_csv(DATA / "dhs_yearbook" / "dhs_state_wide.csv")
    us = w[w.state == "US"].set_index("fiscal_year")
    share = {"lpr_share_of_us": "lpr_total", "nat_share_of_us": "naturalized",
             "students_share_of_us": "i94_students_exchange", "workers_share_of_us": "i94_temp_workers_families",
             "f1m1_share_of_us": "i94_f1_m1", "h1b_share_of_us": "i94_h1b", "f1_share_of_us": "i94_f1",
             "j1_share_of_us": "i94_j1", "l1_share_of_us": "i94_l1", "o1_share_of_us": "i94_o1"}
    for k, c in share.items():
        if c in w:
            w[k] = w[c] / w.fiscal_year.map(us[c])
    cols = {"lpr_total": "dhs_lpr", "lpr_share_of_us": "dhs_lpr_share_of_us", "naturalized": "dhs_naturalized",
            "nat_share_of_us": "dhs_nat_share_of_us", "students_share_of_us": "dhs_i94_students_share_of_us",
            "f1m1_share_of_us": "dhs_i94_f1m1_share_of_us", "workers_share_of_us": "dhs_i94_workers_share_of_us",
            "i94_h1b": "dhs_i94_h1b", "h1b_share_of_us": "dhs_i94_h1b_share_of_us", "i94_f1": "dhs_i94_f1",
            "f1_share_of_us": "dhs_i94_f1_share_of_us", "i94_j1": "dhs_i94_j1", "j1_share_of_us": "dhs_i94_j1_share_of_us",
            "l1_share_of_us": "dhs_i94_l1_share_of_us", "o1_share_of_us": "dhs_i94_o1_share_of_us"}
    m = {"dhs_lpr": ("New lawful permanent residents (green cards), by state of residence (DHS)", "people", F_N),
         "dhs_lpr_share_of_us": ("Share of U.S. new green-card holders (DHS)", PCT, F_PCT),
         "dhs_naturalized": ("People naturalized as U.S. citizens, by state of residence (DHS)", "people", F_N),
         "dhs_nat_share_of_us": ("Share of U.S. naturalizations (DHS)", PCT, F_PCT),
         "dhs_i94_students_share_of_us": ("Share of U.S. student and exchange-visitor admissions, by destination (DHS)", PCT, F_PCT),
         "dhs_i94_f1m1_share_of_us": ("Share of U.S. F-1 and M-1 student admissions, by destination, FY1996-2004 (INS)", PCT, F_PCT),
         "dhs_i94_workers_share_of_us": ("Share of U.S. temporary-worker admissions, by destination (DHS)", PCT, F_PCT),
         "dhs_i94_h1b": ("H-1B worker admissions, by destination state (DHS)", "admissions", F_N),
         "dhs_i94_h1b_share_of_us": ("Share of U.S. H-1B worker admissions, by destination (DHS)", PCT, F_PCT),
         "dhs_i94_f1": ("F-1 student admissions, by destination state (DHS)", "admissions", F_N),
         "dhs_i94_f1_share_of_us": ("Share of U.S. F-1 student admissions, by destination (DHS)", PCT, F_PCT),
         "dhs_i94_j1": ("J-1 exchange-visitor admissions, by destination state (DHS)", "admissions", F_N),
         "dhs_i94_j1_share_of_us": ("Share of U.S. J-1 exchange-visitor admissions, by destination (DHS)", PCT, F_PCT),
         "dhs_i94_l1_share_of_us": ("Share of U.S. L-1 intracompany-transferee admissions, by destination (DHS)", PCT, F_PCT),
         "dhs_i94_o1_share_of_us": ("Share of U.S. O-1 extraordinary-ability worker admissions, by destination (DHS)", PCT, F_PCT)}
    note = ("DHS Office of Homeland Security Statistics, Yearbook of Immigration Statistics (Excel tables where published, "
            "PDF yearbooks otherwise, FY1996-2024), by fiscal year. Green cards and naturalizations by state of residence; no "
            "yearbook table (PDF, Excel or supplemental) splits green cards by state and class of admission, so employment-"
            "based green cards are national only. FY2023-24 values are rounded to the nearest 10. Naturalizations for "
            "FY1994-2003 undercount some states (many records with unknown state). Admissions (I-94) count entries, not people, "
            "by state of intended destination (not required, so 'unknown', which the U.S. total includes, is large). DHS's "
            "counting changed in FY2010 (more complete land admissions) and FY2013-14 (more complete Canadian air and sea "
            "admissions), and FY2020-22 are depressed by COVID-19, so compare admission counts only within FY2010-12, "
            "FY2014-19 and FY2022 on; shares of the U.S. are comparable across years. Students and exchange visitors (F, J, M "
            "with dependants) and temporary workers and families (H, L, O, P, TN, E and others with dependants; E excluded "
            "from FY2024) are DHS's groups for FY2005-24; FY1996-2004 (INS tables) give F-1 and M-1 student principals "
            "instead. H-1B, F-1 and O-1 by state (principals only) come from the class-by-state tables: FY2002 (Table 611) and "
            "FY2005-20 and FY2022-24 (Nonimmigrant Supplemental Table 3); J-1 and L-1 by state are also in the INS tables, "
            "FY1996 and FY1998-2004. No FY1997 or FY2021 class-by-state data, and none for FY2003-04 beyond the INS classes.")
    pct = {k for k in cols if "share" in k}
    return _long(w, "fiscal_year", cols, pct), m, {k: note for k in m}


def iie():
    od = pd.read_csv(DATA / "open_doors" / "open_doors_state_wide.csv")
    na = pd.read_csv(DATA / "nafsa" / "nafsa_state_wide.csv")
    na.loc[(na.state == "MI") & (na.year == 2021), "econ_contribution_usd"] = 965.5e6   # NAFSA prints $695.5M; Open Doors and the totals give $965.5M
    d = pd.concat([_long(od, "year", {"intl_students": "iie_intl_students", "study_abroad": "iie_study_abroad"}),
                   _long(na, "year", {"econ_contribution_usd": "iie_econ_value", "jobs_supported": "iie_jobs"})])
    for k in ("iie_intl_students", "iie_study_abroad", "iie_econ_value", "iie_jobs"):
        MONTHS[k] = {y: f"{y}-{str(y + 1)[-2:]}" for y in range(2015, 2030)}
    m = {"iie_intl_students": ("International students hosted (IIE Open Doors)", "students", F_N),
         "iie_study_abroad": ("U.S. students studying abroad for credit, from the state's institutions (IIE Open Doors)", "students", F_N),
         "iie_econ_value": ("Economic contribution of international students (NAFSA)", "nominal $", F_USD),
         "iie_jobs": ("Jobs supported by international students' spending (NAFSA)", "jobs", F_N)}
    note = ("IIE Open Doors state fact sheets (academic year shown; includes students on OPT) and NAFSA's International Student "
            "Economic Value Tool (spending on tuition and living costs, net of U.S. support; jobs supported). International "
            "students 2019-20 to 2025-26 (Open Doors 2020-2026), study abroad 2017-18 to 2024-25, NAFSA dollars and jobs 2018-19 "
            "to 2024-25. NAFSA's jobs-per-student assumption changed in 2019-20 and 2020-21, so jobs are not strictly comparable "
            "across those years. NAFSA "
            "dollars are printed rounded (to $0.1B for large states). Michigan 2021-22 is corrected to $965.5M (NAFSA's sheet "
            "prints $695.5M; the Open Doors sheet and NAFSA's own total agree with $965.5M).")
    return d, m, {k: note for k in m}


def rd():
    F_M = "${:,.0f}M"
    h = pd.read_csv(DATA / "herd" / "herd_state_wide.csv")
    f = pd.read_csv(DATA / "ffs" / "ffs_state_wide.csv")
    u = pd.read_csv(DATA / "usaspending" / "usaspending_state_wide.csv")
    for c in [c for c in h if c.startswith("rd_exp")]:
        h[c] = h[c] / 1e3                                  # $ thousands -> $ millions
    for c in [c for c in f if c.endswith(("__all", "_higher_ed", "__ag_dod", "__ag_hhs"))]:
        f[c] = f[c] / 1e3
    for c in ("rd_subset", "grants_rd4", "contracts_rd"):
        u[c] = u[c] / 1e6                                  # $ -> $ millions
    h["fed_share"] = h.rd_exp__src_federal / h.rd_exp__all
    h["business_share"] = h.rd_exp__src_business / h.rd_exp__all
    h["state_share"] = h.rd_exp__src_state_local / h.rd_exp__all
    us = h[h.state == "US"].set_index("fiscal_year").rd_exp__all
    h["share_of_us"] = h.rd_exp__all / h.fiscal_year.map(us)
    d = pd.concat([
        _long(h, "fiscal_year", {"rd_exp__all": "rd_herd", "share_of_us": "rd_herd_share_of_us", "fed_share": "rd_herd_fed_share",
                                 "business_share": "rd_herd_business_share", "state_share": "rd_herd_state_share",
                                 "rd_exp__fld_math_cs": "rd_herd_math_cs", "rd_exp__fld_eng": "rd_herd_eng",
                                 "personnel_hc__all": "rd_herd_personnel"},
              {"fed_share", "business_share", "state_share", "share_of_us"}),
        _long(f, "fiscal_year", {"rd_oblig__all": "rd_ffs", "rd_oblig__perf_higher_ed": "rd_ffs_higher_ed", "rd_oblig__ag_dod": "rd_ffs_dod",
                                 "rd_oblig__ag_hhs": "rd_ffs_hhs"}),
        _long(u, "fiscal_year", {"rd_subset": "rd_usa_rd", "grants_rd4": "rd_usa_grants", "contracts_rd": "rd_usa_contracts"})])
    m = {"rd_herd": ("University R&D spending (NSF HERD)", "$ millions", F_M),
         "rd_herd_share_of_us": ("Share of U.S. university R&D (NSF HERD)", PCT, F_PCT),
         "rd_herd_fed_share": ("Federally funded share of university R&D (NSF HERD)", PCT, F_PCT),
         "rd_herd_business_share": ("Business-funded share of university R&D (NSF HERD)", PCT, F_PCT),
         "rd_herd_state_share": ("State- and locally funded share of university R&D (NSF HERD)", PCT, F_PCT),
         "rd_herd_math_cs": ("University R&D in mathematics and computer science (NSF HERD)", "$ millions", F_M),
         "rd_herd_eng": ("University R&D in engineering (NSF HERD)", "$ millions", F_M),
         "rd_herd_personnel": ("University R&D personnel, headcount (NSF HERD)", "people", F_N),
         "rd_ffs": ("Federal R&D obligations to the state (NSF Federal Funds)", "$ millions", F_M),
         "rd_ffs_higher_ed": ("Federal R&D obligations to universities in the state (NSF Federal Funds)", "$ millions", F_M),
         "rd_ffs_dod": ("Defense R&D obligations to the state (NSF Federal Funds)", "$ millions", F_M),
         "rd_ffs_hhs": ("Health (HHS/NIH) R&D obligations to the state (NSF Federal Funds)", "$ millions", F_M),
         "rd_usa_rd": ("Federal research grants and R&D contracts performed in the state (USAspending)", "$ millions", F_M),
         "rd_usa_grants": ("NSF, NIH, NASA and DOE Science grants performed in the state (USAspending)", "$ millions", F_M),
         "rd_usa_contracts": ("Federal R&D contracts performed in the state (USAspending)", "$ millions", F_M)}
    herd = ("NSF NCSES, Higher Education Research and Development Survey, fiscal years, nominal dollars; standard-form "
            "institutions (the short-form-inclusive total differs slightly). FY2003-09 are the predecessor Academic R&D "
            "Expenditures Survey (level break at FY2010). Each year is its own release's value; later releases revise some "
            "states (data/herd/herd_state_wide.csv rd_exp_rev__all). Personnel by state: FY2010-19 and FY2022-24.")
    ffs = ("NSF NCSES, Survey of Federal Funds for R&D: obligations by the state where the work is performed, fiscal years, "
           "nominal dollars, latest volume reporting each year. FY2021 widens coverage to all reporting agencies and moves "
           "FFRDCs under intramural (series break).")
    usa = ("USAspending.gov API, obligations by place of performance, fiscal years, nominal dollars. Grants from NSF, NIH, NASA "
           "and DOE Office of Science (research agencies, including some education awards) plus contracts with an R&D "
           "product/service code from any agency. FY2026 grants are incomplete (re-checked 2026-11-11: no NIH grants, NSF "
           "at 73% of FY2025) and left out; FY2026 R&D contracts are provisional (late reporting).")
    return d, m, {k: (herd if k.startswith("rd_herd") else ffs if k.startswith("rd_ffs") else usa) for k in m}


BUILDERS = {"acs": acs, "naep": naep, "k12": k12, "digest_ps": digest_ps, "gss": gss, "sed": sed, "h1b": h1b, "dol": dol, "opt": opt, "j1": j1,
            "patents": patents, "migration": migration, "scorecard": scorecard, "pseo": pseo,
            "oews": oews, "crdc": crdc, "dhs": dhs, "iie": iie, "rd": rd}


def sheet_panels(states: list[str]) -> list[tuple[str, pd.DataFrame, dict, dict]]:
    """[(src, long rows, measures, notes)] for every source whose outputs exist."""
    out = []
    for src, fn in BUILDERS.items():
        try:
            d, m, notes = fn()
        except (FileNotFoundError, KeyError):   # source not built (or an older output layout)
            continue
        d = _keep_states(d, states)
        m = {k: v for k, v in m.items() if k in set(d.measure)}
        d = d[d.measure.isin(m)]
        out.append((src, d, m, {k: v for k, v in notes.items() if k in m}))   # the chart's source line names the source
    return out
