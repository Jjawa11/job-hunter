# LinkedIn Job Hunter

Automated LinkedIn job scraper that searches for relevant roles, scores them against your resume using AI, and emails you a ranked digest every morning.

## What it does

1. **Scrapes** LinkedIn for cloud/devops/infrastructure roles in Melbourne using your session cookies
2. **Scores** each job using Claude AI against your skills, certifications, and experience
3. **Emails** you a ranked HTML digest with match %, reasons, skill gaps, hiring team, and direct apply links

## Example output

Each job in the digest shows:
- Match score (0–100%) and recommendation (Strong / Good / Possible / Weak)
- Job title, company, location, salary, workplace type
- Why it matched — skills that align
- Skill gaps — what's missing
- Hiring team LinkedIn profiles
- Recruiter email if listed in the job description
- One-click apply link

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Jjawa11/job-hunter
cd job-hunter
```

### 2. Install dependencies

```bash
pip3 install linkedin-api anthropic python-dotenv requests
```

### 3. Configure your environment

```bash
cp .env.example .env
```

Fill in your values in `.env`:

```
LINKEDIN_LI_AT=your_li_at_cookie
LINKEDIN_JSESSIONID=your_jsessionid_cookie
ANTHROPIC_API_KEY=your_anthropic_api_key
EMAIL_SENDER=your.gmail@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
```

### 4. Get your LinkedIn cookies

1. Open Chrome → go to `linkedin.com` → make sure you're logged in
2. Press `Cmd + Option + I` (Mac) or right-click → Inspect
3. Go to **Application** tab → **Cookies** → `www.linkedin.com`
4. Find `li_at` → copy the value → paste into `.env`
5. Find `JSESSIONID` → copy the value → paste into `.env`

> Your cookies act as your login session. Keep them private — never commit `.env` to GitHub.

### 5. Get your Anthropic API key

Sign up at [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key. New accounts get $5 free credit which covers months of daily runs.

### 6. Set up Gmail App Password (optional — for email sending)

1. Go to `myaccount.google.com` → Security
2. Enable 2-Step Verification if not already on
3. Search "App passwords" → Generate one named "Job Hunter"
4. Paste the 16-character password into `.env` as `EMAIL_PASSWORD`

> If you skip email setup, run with `--preview` to save an HTML file instead.

---

## Usage

**Test locally — save HTML preview, no email:**
```bash
python3 job_hunter.py --debug --preview
```

**Run once and send email:**
```bash
python3 job_hunter.py
```

**Verbose output to see what's being scraped:**
```bash
python3 job_hunter.py --debug
```

After running, open `digest_preview.html` in your browser to see the digest layout.

---

## Automate with GitHub Actions

Push to a **private** GitHub repo, add your secrets, and it runs every morning at 8am AEST automatically — no server needed.

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "feat: initial job hunter"
```

Then publish to a private repo via VS Code (`Cmd + Shift + P` → Publish to GitHub → Private).

### 2. Add secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → add:

| Secret | Value |
|--------|-------|
| `LINKEDIN_LI_AT` | Your li_at cookie |
| `LINKEDIN_JSESSIONID` | Your JSESSIONID cookie |
| `ANTHROPIC_API_KEY` | Your Anthropic key |
| `EMAIL_SENDER` | Your Gmail address |
| `EMAIL_PASSWORD` | Your Gmail App Password |

### 3. Trigger manually to test

Go to **Actions** tab → **Daily LinkedIn Job Digest** → **Run workflow** → **Run workflow**

Watch the live logs to confirm everything works. After that it runs automatically every day.

---

## Customise

Edit the config at the top of `job_hunter.py`:

```python
# Change search terms
SEARCH_QUERIES = [
    "azure cloud engineer",
    "devops engineer",
    ...
]

# Change minimum match threshold (default 50%)
"min_match_score": 50,

# Change location
LOCATION = "Melbourne, Victoria, Australia"

# Change results per query (default 10)
MAX_PER_QUERY = 10
```

---

## Project structure

```
job-hunter/
├── job_hunter.py          # Main script — scrape, score, email
├── .env.example           # Environment variables template
├── .gitignore             # Keeps .env out of git
├── README.md
└── .github/
    └── workflows/
        └── daily-digest.yml   # GitHub Actions — runs 8am AEST daily
```

---

## Important notes

- Keep this repo **private** — your LinkedIn cookies give full account access
- LinkedIn cookies expire periodically — refresh `li_at` and `JSESSIONID` if scraping stops working
- This tool is for personal use only
- Run responsibly — the script has built-in delays to avoid rate limiting

---

## Built by

**Jayant Jawa** — Senior Azure Cloud Engineer, Melbourne
[jjawa11.github.io](https://jjawa11.github.io) · [LinkedIn](https://linkedin.com/in/jayant-jawa-8a11101b9) · [GitHub](https://github.com/Jjawa11)
