#!/usr/bin/env python3
"""
LinkedIn Job Hunter for Jayant Jawa
-------------------------------------
Uses your LinkedIn session cookie (li_at) to search for
personalised job matches, score them with AI, and email a digest.

Usage:
    python3 job_hunter.py              # Run once + send email
    python3 job_hunter.py --debug      # Verbose output
    python3 job_hunter.py --preview    # Save HTML only, no email
"""

import os
import re
import json
import time
import smtplib
import argparse
import requests
import anthropic

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from linkedin_api import Linkedin
from dotenv import load_dotenv

load_dotenv()

# YOUR PROFILE
PROFILE = {
    "name": "Jayant Jawa",
    "email": "jawa.jayant.jj@gmail.com",
    "title": "Senior Azure Cloud Engineer",
    "experience_years": 4,
    "location": "Melbourne, VIC, Australia",
    "linkedin": "https://linkedin.com/in/jayant-jawa-8a11101b9",
    "portfolio": "https://jjawa11.github.io",
    "skills": [
        "Azure", "Terraform", "DevOps", "IaC", "GitHub Actions", "Azure DevOps",
        "PowerShell", "Bash", "Python", "Docker", "Azure Virtual Desktop", "AVD",
        "AKS", "Azure Entra ID", "Key Vault", "VNet", "NSG", "Azure Firewall",
        "Application Gateway", "WAF", "Azure Migrate", "DMS", "SQL MI",
        "Azure Monitor", "Log Analytics", "Azure Policy", "RBAC", "Landing Zones",
        "CIS Hardening", "CI/CD", "GitHub Copilot", "ARM Templates", "Bicep",
        "Hyper-V", "VMware", "Physical Server Migration", "IaaS", "PaaS",
        "Conditional Access", "Defender for Cloud", "FinOps", "Zero Trust",
        "GitLab", "GEI", "GitHub CLI", "AWS", "GCP", "Kubernetes",
    ],
    "certifications": [
        "AZ-104", "AZ-305", "AZ-303", "AZ-140", "AZ-103",
        "AZ-900", "SC-900", "GitHub Foundations", "GitHub Copilot"
    ],
    "min_match_score": 50,
}

# SEARCH CONFIG
SEARCH_QUERIES = [
    "azure",
    "cloud engineer",
    "devops engineer",
    "infrastructure engineer",
    "platform engineer",
    "terraform",
    "site reliability engineer",
]
EXPERIENCE_LEVELS = ["3", "4"]
JOB_TYPES         = ["F", "C"]
LOCATION          = "Melbourne, Victoria, Australia"
LISTED_WITHIN     = 7 * 24 * 60 * 60
MAX_PER_QUERY     = 15


# STEP 1 — SCRAPE
def scrape_linkedin(debug=False):
    li_at      = os.getenv("LINKEDIN_LI_AT", "").strip()
    jsessionid = os.getenv("LINKEDIN_JSESSIONID", "").strip()
    li_email   = os.getenv("LINKEDIN_EMAIL", "")
    li_pass    = os.getenv("LINKEDIN_PASSWORD", "")

    if not li_at and not (li_email and li_pass):
        raise ValueError("Set LINKEDIN_LI_AT (and LINKEDIN_JSESSIONID) in .env")

    print("Connecting to LinkedIn...")
    try:
        if li_at:
            session = requests.Session()
            session.cookies.set("li_at",      li_at,      domain=".linkedin.com")
            session.cookies.set("JSESSIONID", jsessionid, domain=".linkedin.com")
            session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "csrf-token": jsessionid.strip('"'),
            })
            api = Linkedin("", "", cookies=session.cookies)
        else:
            api = Linkedin(li_email, li_pass)
        print("Connected to LinkedIn\n")
    except Exception as e:
        raise ConnectionError(f"LinkedIn auth failed: {e}")

    all_jobs = []
    seen_ids = set()

    for query in SEARCH_QUERIES:
        print(f"  Searching: '{query}'")
        try:
            results = api.search_jobs(
                keywords=query,
                limit=10,
            )
            print(f"     -> {len(results)} results returned")

            for r in results:
                try:
                    entity_urn = r.get("entityUrn", "") or r.get("trackingUrn", "")
                    job_id = entity_urn.split(":")[-1] if entity_urn else ""

                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    title = r.get("title", "Unknown")

                    job = {
                        "job_id":          job_id,
                        "title":           title,
                        "company":         "Unknown",
                        "location":        LOCATION,
                        "posted":          "Recently",
                        "apply_url":       f"https://www.linkedin.com/jobs/view/{job_id}/",
                        "description":     "",
                        "salary":          "Not specified",
                        "workplace_type":  "",
                        "recruiter_email": "",
                        "hiring_team":     [],
                    }

                    if debug:
                        print(f"       Fetching details: {title}")

                    try:
                        details = api.get_job(job_id)
                        if details:
                            job = _enrich(job, details, debug)
                    except Exception as e:
                        if debug:
                            print(f"       get_job failed: {e}")

                    all_jobs.append(job)
                    time.sleep(0.5)

                except Exception as e:
                    if debug:
                        print(f"       Parse error: {e}")
                    continue

        except Exception as e:
            print(f"     Search error: {e}")
            continue

        time.sleep(2)

    print(f"\nTotal unique jobs scraped: {len(all_jobs)}")
    return all_jobs


def _enrich(job, data, debug=False):
    try:
        # Company
        company_details = data.get("companyDetails", {})
        for key, val in company_details.items():
            name = (
                val.get("companyResolutionResult", {}).get("name")
                or val.get("company", {}).get("name")
            )
            if name:
                job["company"] = name
                break
        if job["company"] == "Unknown":
            job["company"] = data.get("companyName", "Unknown")

        # Location
        job["location"] = data.get("formattedLocation", job["location"])

        # Posted date
        listed_at = data.get("listedAt", 0)
        if listed_at:
            job["posted"] = _fmt_date(listed_at)

        # Description
        desc = data.get("description", {})
        if isinstance(desc, dict):
            job["description"] = desc.get("text", "")[:3000]
        elif isinstance(desc, str):
            job["description"] = desc[:3000]

        # Salary
        salary_info = data.get("salaryInsights", {})
        breakdown   = salary_info.get("compensationBreakdown", [{}])
        if breakdown:
            lo = breakdown[0].get("minSalary")
            hi = breakdown[0].get("maxSalary")
            if lo and hi:
                job["salary"] = f"${int(lo):,} - ${int(hi):,}"

        # Workplace type
        wt = data.get("workplaceTypesResolutionResults", {})
        if wt:
            first = next(iter(wt.values()), {})
            job["workplace_type"] = first.get("localizedName", "")

        # Hiring team
        for member in data.get("hiringTeam", [])[:3]:
            entity = member.get("com.linkedin.voyager.jobs.HiringTeamMember", member)
            mp    = entity.get("memberProfile", {})
            name  = f"{mp.get('firstName','')} {mp.get('lastName','')}".strip()
            pub   = mp.get("publicIdentifier", "")
            if name:
                job["hiring_team"].append({
                    "name":    name,
                    "profile": f"https://www.linkedin.com/in/{pub}/" if pub else "",
                })

        # Email from description
        emails = re.findall(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
            job["description"]
        )
        if emails:
            job["recruiter_email"] = emails[0]

    except Exception as e:
        if debug:
            print(f"       Enrich error: {e}")
    return job


def _fmt_date(ts_ms):
    try:
        dt    = datetime.fromtimestamp(ts_ms / 1000)
        delta = datetime.now() - dt
        if delta.days == 0: return "Today"
        if delta.days == 1: return "Yesterday"
        return f"{delta.days} days ago"
    except Exception:
        return "Recently"


# STEP 2 — SCORE WITH AI
def score_jobs(jobs, debug=False):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    scored = []

    print(f"\nScoring {len(jobs)} jobs with AI...")

    for i, job in enumerate(jobs):
        print(f"  [{i+1}/{len(jobs)}] {job['title']} @ {job['company']}")
        try:
            prompt = f"""Score this job against the candidate. Return ONLY valid JSON, no markdown.

CANDIDATE:
- Title: {PROFILE['title']}
- Experience: {PROFILE['experience_years']}+ years Azure cloud delivery
- Location: {PROFILE['location']}
- Skills: {', '.join(PROFILE['skills'][:35])}
- Certs: {', '.join(PROFILE['certifications'])}

JOB:
- Title: {job['title']}
- Company: {job['company']}
- Location: {job['location']} {job.get('workplace_type','')}
- Salary: {job.get('salary','Not specified')}
- Description: {job.get('description','No description available')[:1500]}

Return exactly this JSON:
{{
  "match_score": <0-100>,
  "recommendation": "<STRONG MATCH|GOOD MATCH|POSSIBLE MATCH|WEAK MATCH>",
  "matched_skills": ["skill1","skill2","skill3"],
  "missing_skills": ["gap1","gap2"],
  "one_liner": "<one sentence why or why not>",
  "recruiter_email": "<email from description if found, else empty string>"
}}"""

            resp   = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            text   = re.sub(r"```json|```", "", resp.content[0].text).strip()
            result = json.loads(text)

            job["match_score"]    = result.get("match_score", 0)
            job["recommendation"] = result.get("recommendation", "WEAK MATCH")
            job["matched_skills"] = result.get("matched_skills", [])
            job["missing_skills"] = result.get("missing_skills", [])
            job["one_liner"]      = result.get("one_liner", "")
            if result.get("recruiter_email") and not job.get("recruiter_email"):
                job["recruiter_email"] = result["recruiter_email"]

            if debug:
                print(f"     -> {job['match_score']}% {job['recommendation']}")

        except Exception as e:
            print(f"     Scoring failed: {e}")
            job.update({"match_score":0,"recommendation":"WEAK MATCH",
                        "matched_skills":[],"missing_skills":[],"one_liner":""})

        scored.append(job)

    filtered = [j for j in scored if j["match_score"] >= PROFILE["min_match_score"]]
    filtered.sort(key=lambda x: x["match_score"], reverse=True)
    print(f"\n{len(filtered)} jobs above {PROFILE['min_match_score']}% match threshold")
    return filtered


# STEP 3 — BUILD & SEND EMAIL
BADGE = {
    "STRONG MATCH":   ("#065f46", "#d1fae5", "STRONG MATCH"),
    "GOOD MATCH":     ("#1e3a5f", "#dbeafe", "GOOD MATCH"),
    "POSSIBLE MATCH": ("#78350f", "#fef3c7", "POSSIBLE MATCH"),
    "WEAK MATCH":     ("#6b7280", "#f3f4f6", "WEAK MATCH"),
}


def _card(job):
    rec       = job.get("recommendation", "WEAK MATCH")
    tc, bg, _ = BADGE.get(rec, ("#6b7280","#f3f4f6","WEAK MATCH"))
    score     = job.get("match_score", 0)

    skills_html = "".join(
        f'<span style="display:inline-block;background:#e0f2fe;color:#0369a1;'
        f'font-size:11px;padding:2px 8px;border-radius:20px;margin:2px 2px 2px 0;">'
        f'{s}</span>'
        for s in job.get("matched_skills", [])[:5]
    )

    missing_html = ""
    if job.get("missing_skills"):
        missing_html = (
            f'<p style="margin:8px 0 0;font-size:12px;color:#9ca3af;">'
            f'Gaps: {", ".join(job["missing_skills"][:3])}</p>'
        )

    hiring_html = ""
    if job.get("hiring_team"):
        links = []
        for m in job["hiring_team"][:2]:
            if m.get("profile"):
                links.append(
                    f'<a href="{m["profile"]}" style="color:#2563eb;font-size:12px;">'
                    f'{m["name"]}</a>'
                )
            else:
                links.append(f'<span style="font-size:12px;color:#374151;">{m["name"]}</span>')
        hiring_html = (
            f'<p style="margin:8px 0 0;font-size:12px;">'
            f'<strong>Hiring team:</strong> {"  |  ".join(links)}</p>'
        )

    email_html = ""
    if job.get("recruiter_email"):
        email_html = (
            f'<p style="margin:6px 0 0;font-size:12px;">'
            f'Email: <a href="mailto:{job["recruiter_email"]}" style="color:#2563eb;">'
            f'{job["recruiter_email"]}</a></p>'
        )

    salary_str = f' | {job["salary"]}' if job.get("salary") and job["salary"] != "Not specified" else ""
    wt_str     = f' | {job["workplace_type"]}' if job.get("workplace_type") else ""

    return f'''
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;
            margin-bottom:16px;overflow:hidden;font-family:-apple-system,sans-serif;">
  <div style="background:{bg};padding:10px 16px;
              display:flex;justify-content:space-between;align-items:center;">
    <span style="font-weight:700;color:{tc};font-size:13px;">{rec}</span>
    <span style="font-size:24px;font-weight:800;color:{tc};">{score}%</span>
  </div>
  <div style="padding:14px 16px;">
    <h3 style="margin:0 0 4px;font-size:16px;color:#111827;">{job["title"]}</h3>
    <p style="margin:0;font-size:13px;color:#6b7280;">
      {job["company"]} | {job["location"]}{wt_str}{salary_str} | {job.get("posted","Recently")}
    </p>
    <p style="margin:10px 0 6px;font-size:13px;color:#374151;font-style:italic;">
      "{job.get("one_liner","")}"
    </p>
    <div style="margin:6px 0;">{skills_html}</div>
    {missing_html}
    {hiring_html}
    {email_html}
    <div style="margin-top:12px;">
      <a href="{job["apply_url"]}"
         style="background:#2563eb;color:#fff;padding:8px 20px;border-radius:6px;
                text-decoration:none;font-size:13px;font-weight:600;
                display:inline-block;">
        View and Apply
      </a>
    </div>
  </div>
</div>'''


def build_html(jobs):
    date_str = datetime.now().strftime("%A, %d %B %Y")
    strong   = [j for j in jobs if j.get("recommendation") == "STRONG MATCH"]
    good     = [j for j in jobs if j.get("recommendation") == "GOOD MATCH"]
    possible = [j for j in jobs if j.get("recommendation") == "POSSIBLE MATCH"]
    cards    = "".join(_card(j) for j in jobs)

    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px;">
  <div style="background:#1e3a5f;border-radius:16px;padding:28px 32px;
              margin-bottom:20px;color:#fff;">
    <h1 style="margin:0 0 6px;font-size:22px;">LinkedIn Job Digest</h1>
    <p style="margin:0;opacity:.85;font-size:13px;">
      {date_str} - Hey Jayant, here are your matches
    </p>
  </div>
  <table width="100%" cellpadding="8" cellspacing="0" style="margin-bottom:20px;">
    <tr>
      <td style="background:#d1fae5;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:26px;font-weight:800;color:#065f46;">{len(strong)}</div>
        <div style="font-size:11px;color:#065f46;font-weight:600;">Strong Matches</div>
      </td>
      <td width="12"></td>
      <td style="background:#dbeafe;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:26px;font-weight:800;color:#1e3a5f;">{len(good)}</div>
        <div style="font-size:11px;color:#1e3a5f;font-weight:600;">Good Matches</div>
      </td>
      <td width="12"></td>
      <td style="background:#fef3c7;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:26px;font-weight:800;color:#78350f;">{len(possible)}</div>
        <div style="font-size:11px;color:#78350f;font-weight:600;">Possible Matches</div>
      </td>
    </tr>
  </table>
  {cards}
  <div style="text-align:center;padding:16px;color:#9ca3af;font-size:11px;">
    Sent by your Job Hunter |
    <a href="{PROFILE['portfolio']}" style="color:#2563eb;">Portfolio</a> |
    <a href="{PROFILE['linkedin']}"  style="color:#2563eb;">LinkedIn</a>
  </div>
</div>
</body></html>'''


def send_digest(jobs, preview_only=False):
    html = build_html(jobs)
    with open("digest_preview.html", "w") as f:
        f.write(html)
    print("Saved digest_preview.html")

    if preview_only:
        print("Preview mode - not sending email.")
        return

    sender   = os.getenv("EMAIL_SENDER", "")
    password = os.getenv("EMAIL_PASSWORD", "")

    if not sender or not password:
        print("EMAIL_SENDER / EMAIL_PASSWORD not set - preview saved only.")
        return

    subject = (
        f"LinkedIn Job Digest {datetime.now().strftime('%d %b')} "
        f"- {len(jobs)} matches"
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = PROFILE["email"]
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(sender, password)
            s.sendmail(sender, PROFILE["email"], msg.as_string())
        print(f"Digest sent to {PROFILE['email']}")
    except Exception as e:
        print(f"Email error: {e}")


# MAIN
def main():
    parser = argparse.ArgumentParser(description="LinkedIn Job Hunter")
    parser.add_argument("--debug",   action="store_true", help="Verbose output")
    parser.add_argument("--preview", action="store_true", help="HTML only, no email")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f"  LinkedIn Job Hunter - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}\n")

    jobs    = scrape_linkedin(debug=args.debug)
    matched = score_jobs(jobs, debug=args.debug)
    send_digest(matched, preview_only=args.preview)

    print(f"\n{'='*55}")
    print(f"  Done. {len(matched)} jobs in your digest.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()