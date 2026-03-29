from jobspy import scrape_jobs
import uuid, json, pathlib, math


# ── NaN GUARD ──────────────────────────────────────
def _v(val):
    """Convert NaN / pandas NA / inf to None; otherwise return the value."""
    try:
        if val is None:
            return None
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        # catches pandas NA / NaT etc.
        import pandas as pd
        if pd.isna(val):
            return None
    except Exception:
        pass
    return val


def _num(val):
    """Return an int from val, or 0 if it's NaN/None/invalid."""
    v = _v(val)
    if v is None:
        return 0
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0

# ── CONFIG ─────────────────────────────────────────
CONFIG = {
    "results_wanted": 15,
    "sites": ["linkedin", "indeed", "glassdoor", "zip_recruiter", "google"],
}

# ── SIMPLE IN-MEMORY CACHE ─────────────────────────
CACHE = {}


# ── FALLBACK: load from saved jobs.json ────────────
def _fallback_jobs(search_query=None, location=None):
    """
    Load jobs from local jobs.json as a fallback when live scraping fails.
    Optionally filters by search_query keyword match.
    """
    try:
        data = json.loads(pathlib.Path("jobs.json").read_text())
        jobs = []
        for search in data.get("searches", []):
            jobs.extend(search.get("jobs", []))

        # Deduplicate by URL
        seen, out = set(), []
        for j in jobs:
            url = j.get("url")
            if url not in seen:
                seen.add(url)
                # Ensure all expected fields exist
                j.setdefault("posted_at", "unknown")
                j.setdefault("source", "cached")
                j.setdefault("salary", None)
                j.setdefault("skills", [])
                j.setdefault("viewed", False)
                j.setdefault("applied", False)
                desc = j.get("description", "")
                j.setdefault(
                    "description_preview",
                    desc[:200].rstrip() + ("…" if len(desc) > 200 else ""),
                )
                out.append(j)

        # Simple keyword filter so cached results feel relevant
        if search_query:
            kw = search_query.lower()
            filtered = [
                j for j in out
                if kw in (j.get("title") or "").lower()
                or kw in (j.get("description") or "").lower()
            ]
            if filtered:
                return filtered

        return out
    except Exception as e:
        print("⚠️  Could not load fallback jobs.json:", e)
        return []


# ── MAIN SCRAPE FUNCTION ───────────────────────────
def run_scrape(search_query=None, location=None, job_type=None):
    key = f"{search_query}-{location}-{job_type}"

    # ⚡ CACHE HIT
    if key in CACHE:
        print("⚡ Returning cached jobs")
        return CACHE[key]

    print("🔍 Scraping fresh jobs from LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google...")

    scrape_kwargs = dict(
        site_name=CONFIG["sites"],
        search_term=search_query,
        location=location,
        results_wanted=CONFIG["results_wanted"],
        linkedin_fetch_description=True,
    )
    if job_type:
        scrape_kwargs["job_type"] = job_type

    try:
        jobs_df = scrape_jobs(**scrape_kwargs)
        jobs_df = jobs_df.drop_duplicates(subset=["job_url"])
        jobs_df = jobs_df.where(jobs_df.notna(), other=None)

        if jobs_df.empty:
            raise ValueError("Scraper returned 0 results")

        jobs_out = []
        for _, row in jobs_df.iterrows():
            raw_desc = _v(row.get("description")) or ""
            min_amt  = _v(row.get("min_amount"))
            max_amt  = _v(row.get("max_amount"))

            if min_amt is not None:
                salary = f"${_num(min_amt):,}"
                salary += f" – ${_num(max_amt):,}" if max_amt is not None else "+"
            else:
                salary = None

            job = {
                "id":                  str(uuid.uuid4()),
                "title":               _v(row.get("title"))    or None,
                "company":             _v(row.get("company"))  or None,
                "location":            _v(row.get("location")) or None,
                "description":         raw_desc[:3000],
                "description_preview": raw_desc[:200].rstrip() + ("…" if len(raw_desc) > 200 else ""),
                "posted_at":           str(_v(row.get("date_posted")) or "unknown"),
                "url":                 _v(row.get("job_url"))  or None,
                "source":              _v(row.get("site"))     or None,
                "salary":              salary,
                "skills":  [],
                "viewed":  False,
                "applied": False,
            }
            jobs_out.append(job)

        CACHE[key] = jobs_out
        print(f"✅ Returning {len(jobs_out)} live jobs\n")
        return jobs_out

    except Exception as e:
        print(f"⚠️  Live scraping failed ({e}). Falling back to jobs.json …")
        fallback = _fallback_jobs(search_query, location)
        if fallback:
            print(f"📦 Returning {len(fallback)} cached jobs from jobs.json")
        else:
            print("❌ No fallback jobs available either.")
        return fallback