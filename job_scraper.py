from jobspy import scrape_jobs
import json
from datetime import datetime
import uuid
import ollama
import re
import os
import pandas as pd

# ---------------- CONFIG ----------------
CONFIG = {
    "search_query": "software engineer intern",
    "location": "remote",
    "results_wanted": 30,
    "batch_size": 5,
    "max_new_jobs": 5,
    "output_file": "jobs.json",
    "llm_model": "qwen:1.8b",
    "desc_char_limit": 800,
}

search_query   = CONFIG["search_query"]
location       = CONFIG["location"]
results_wanted = CONFIG["results_wanted"]
BATCH_SIZE     = CONFIG["batch_size"]
OUTPUT_FILE    = CONFIG["output_file"]

# ---------------- SCRAPE ----------------
jobs_df = scrape_jobs(
    site_name=["indeed", "google", "linkedin", "glassdoor"],
    search_term=search_query,
    location=location,
    results_wanted=results_wanted,
)

# ---------------- HELPERS ----------------
def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def extract_skills_batch(descriptions):
    descriptions = [
        str(d)[:CONFIG["desc_char_limit"]] if d and d != "nan" else ""
        for d in descriptions
    ]

    combined = "\n\n---JOB---\n\n".join(descriptions)

    prompt = f"""
Extract key technical skills for EACH job description.

Rules:
- Return ONLY valid JSON
- No explanation
- Output format:
[
  ["python", "fastapi"],
  ["react", "node"]
]
- The outer array must have exactly {len(descriptions)} inner arrays, one per job.

Descriptions:
{combined}
"""

    try:
        response = ollama.chat(
            model=CONFIG["llm_model"],
            messages=[{"role": "user", "content": prompt}]
        )

        content = response["message"]["content"]

        # robust JSON extraction
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            # ensure length matches before returning
            if len(parsed) == len(descriptions):
                return parsed
            else:
                print(f"⚠️  LLM returned {len(parsed)} skill lists for {len(descriptions)} jobs — padding/trimming")
                # pad with empty lists if too short, trim if too long
                parsed += [[] for _ in range(len(descriptions) - len(parsed))]
                return parsed[:len(descriptions)]

    except Exception as e:
        print("⚠️ Batch LLM error:", e)

    return [[] for _ in descriptions]


# ---------------- PROCESS ----------------
jobs_df = jobs_df.drop_duplicates(subset=["job_url"])

# ---------------- LOAD SEEN URLS FIRST ----------------
seen_urls = set()

if os.path.exists(OUTPUT_FILE):
    try:
        with open(OUTPUT_FILE, "r") as f:
            data = json.load(f)
            for search in data.get("searches", []):
                for job in search.get("jobs", []):
                    seen_urls.add(job["url"])
    except:
        pass

# ---------------- FILTER NEW JOBS BEFORE LLM ----------------
# Only keep rows whose URL hasn't been seen before
new_rows = [
    row for _, row in jobs_df.iterrows()
    if row.get("job_url") not in seen_urls
]
new_rows = new_rows[:CONFIG["max_new_jobs"]]  # cap via config, not hardcoded

# extract descriptions only for new jobs
descriptions = [
    str(row.get("description")) if pd.notna(row.get("description")) else ""
    for row in new_rows
]

print(f"⚡ Running batched LLM extraction on {len(descriptions)} new jobs...")

skills_list = []

for chunk_descs in chunk_list(descriptions, BATCH_SIZE):
    skills_list.extend(extract_skills_batch(chunk_descs))

# ---------------- BUILD OUTPUT ----------------
search_id   = str(uuid.uuid4())
search_date = datetime.now().isoformat()

search_data = {
    "search_id": search_id,
    "query": search_query,
    "location": location,
    "scraped_at": search_date,
    "jobs": []
}

for i, (row, skills) in enumerate(zip(new_rows, skills_list)):
    print(f"✅ Processed job {i + 1}/{len(new_rows)}")

    job = {
        "id": str(uuid.uuid4()),
        "title": row.get("title"),
        "company": row.get("company"),
        "location": row.get("location"),
        "description": (row.get("description") or "")[:1000],
        "posted_at": str(row.get("date_posted") or "unknown"),
        "url": row.get("job_url"),
        "skills": list(set([s.lower().strip() for s in skills]))
    }

    search_data["jobs"].append(job)


# ---------------- SAVE (APPEND MODE) ----------------
if os.path.exists(OUTPUT_FILE):
    try:
        content = open(OUTPUT_FILE).read().strip()
        data = json.loads(content) if content else {"searches": []}
    except:
        data = {"searches": []}
else:
    data = {"searches": []}

if "searches" not in data:
    data["searches"] = []

data["searches"].append(search_data)

with open(OUTPUT_FILE, "w") as f:
    json.dump(data, f, indent=2)

print(f"\n✅ Saved search with {len(search_data['jobs'])} jobs\n")